from __future__ import annotations

import asyncio
import threading

from loguru import logger
from PIL import UnidentifiedImageError

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.saucenao import SauceNao
from szurubooru_toolkit.saucenao import SauceNaoCooldown
from szurubooru_toolkit.szurubooru import Post
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import get_cached_implications
from szurubooru_toolkit.utils import prepare_post
from szurubooru_toolkit.utils import run_concurrently
from szurubooru_toolkit.utils import sanitize_tags
from szurubooru_toolkit.utils import search_boorus
from szurubooru_toolkit.utils import shrink_img
from szurubooru_toolkit.utils import statistics

deepbooru = None
_deepbooru_lock = threading.Lock()

# Shared across all main() invocations in this process, so concurrent upload
# workers which each call auto_tagger.main() share the SauceNAO rate limit state.
_cooldown = SauceNaoCooldown()
_limit_event = threading.Event()


def get_saucenao_results(sauce: SauceNao, post: Post, image: bytes, cooldown: SauceNaoCooldown) -> tuple[dict, bool]:
    """
    Retrieves the SauceNAO results for a given image.

    This function sends the image to the SauceNAO API using the provided SauceNao object. It then processes the results
    and searches the boorus for additional data. If the SauceNAO limit has been reached, it sets a flag to indicate this.

    Args:
        sauce (SauceNao): A SauceNao object to use for the SauceNAO API.
        post (Post): A szurubooru Post object representing the post to be uploaded.
        image (bytes): The image to be uploaded to SauceNAO.
        cooldown (SauceNaoCooldown): Shared cooldown gate for the SauceNAO short limit.

    Returns:
        tuple[dict, bool]: A tuple containing the results and a boolean indicating whether the SauceNAO limit has
                           been reached.
    """

    results = {}
    limit_reached = False
    matches, limit_short, limit_long = asyncio.run(sauce.get_metadata(post.content_url, image))

    for index, data in matches.items():
        if data and index != 'pixiv':
            results.update(asyncio.run(search_boorus(data['site'], f'id:{str(data["post_id"])}', 1, 0, credentials=config.credentials)))

        if data and index == 'pixiv':
            results[index] = data

    if not limit_long == 0:
        # Pause SauceNAO requests for all workers after the short limit has been reached
        if limit_short == 0:
            logger.debug('Short limit reached for SauceNAO, cooling down for 35s...')
            cooldown.trigger(35)
    else:
        limit_reached = True
        logger.info('Your daily SauceNAO limit has been reached. Consider upgrading your account.')

    if limit_reached and config.auto_tagger['deepbooru']:
        config.auto_tagger['saucenao'] = False
        logger.info('Continuing tagging with Deepbooru only...')

    return results, limit_reached


def set_tags_from_relations(post: Post) -> None:
    """
    Copies artist, character, and parody tags from related posts.

    This function is useful for FANBOX/Fantia sets where only the main post is uploaded to a Booru. It iterates over the
    relations of the provided post and retrieves each related post from szurubooru. It then iterates over the tags of the
    related post and adds any artist, character, or series tag to the tags of the provided post.

    Args:
        post (Post): A szurubooru Post object representing the post to which to add tags.

    Returns:
        None
    """

    for relation in post.relations:
        result = szuru.get_post(relation['id'])

        for relation_tag in result.micro_tags:
            if relation_tag.category not in ('default', 'meta'):
                post.tags.append(relation_tag.primary_name)


def print_statistics(total_posts):
    """
    Prints the statistics of the tagging process.

    This function retrieves the statistics of the tagging process by calling the `statistics` function. It then logs
    these statistics, including the total number of posts, the number of tagged posts, the number of posts tagged by
    Deepbooru, the number of untagged posts, and the number of skipped posts.

    Args:
        total_posts (int): The total number of posts processed.

    Returns:
        None
    """

    total_tagged, total_deepbooru, total_untagged, total_skipped = statistics()

    logger.success('Script has finished tagging.')
    logger.info(f'Total:     {total_posts}')
    logger.info(f'Tagged:    {str(total_tagged)}')
    logger.info(f'Deepbooru: {str(total_deepbooru)}')
    logger.info(f'Untagged:  {str(total_untagged)}')
    logger.info(f'Skipped:   {str(total_skipped)}')


def process_post(  # noqa C901
    post: Post,
    sauce: SauceNao,
    cooldown: SauceNaoCooldown,
    limit_event: threading.Event,
    add_tags: list,
    remove_tags: list,
    md5: str = '',
    file_to_upload: bytes = None,
) -> None:
    """
    Tags a single post with tags from the MD5 search, SauceNAO and/or Deepbooru.

    This is the per-post unit of work; multiple posts are processed concurrently by
    `main`. The shared `limit_event` signals that the SauceNAO daily limit has been
    reached, the shared `cooldown` paces requests after the short limit.

    Args:
        post (Post): The szurubooru post to tag.
        sauce (SauceNao): Shared SauceNAO client (None if SauceNAO is disabled).
        cooldown (SauceNaoCooldown): Shared cooldown gate for SauceNAO requests.
        limit_event (threading.Event): Set once the SauceNAO daily limit is reached.
        add_tags (list): Tags to add to the post.
        remove_tags (list): Tags to remove from the post.
        md5 (str, optional): Overrides the MD5 hash to search boorus with. Defaults to ''.
        file_to_upload (bytes, optional): Locally available file content, skips the download. Defaults to None.

    Returns:
        None
    """

    # Once the daily SauceNAO limit is reached and Deepbooru is disabled,
    # the remaining posts are counted as untagged (same as the sequential break before)
    if limit_event.is_set() and not config.auto_tagger['deepbooru']:
        statistics(untagged=1)
        return

    # Search boorus by md5 hash of the file
    if config.auto_tagger['md5_search']:
        md5_results = asyncio.run(search_boorus('all', 'md5:' + (md5 or post.md5), 1, 0, credentials=config.credentials))

        if md5_results:
            tags_by_md5, sources, post.rating = prepare_post(md5_results, config)
            post.source = collect_sources(*sources, *post.source.splitlines())
        else:
            tags_by_md5 = []
    else:
        tags_by_md5 = []

    # Download the file from szurubooru if its not already locally present.
    # This might be the case if this function was called from upload_media.
    if not file_to_upload:
        if (
            (not config.globals['public'] or config.auto_tagger['deepbooru']) or config.auto_tagger['deepbooru_forced']
        ) and post.type != 'video':
            image = download_media(post.content_url, post.md5)
            # Shrink files >2MB
            try:
                if len(image) > 2000000:
                    image = shrink_img(image, resize=True, convert=True)
            except UnidentifiedImageError:
                logger.debug('Could not shrink image')
        else:
            image = None  # Let SauceNAO download the image from public szurubooru URL
    else:
        image = file_to_upload

    # Search SauceNAO with file
    if config.auto_tagger['saucenao'] and post.type != 'video' and not limit_event.is_set():
        cooldown.wait()
        sauce_results, limit_reached = get_saucenao_results(sauce, post, image, cooldown)

        if limit_reached:
            limit_event.set()

        if sauce_results:
            tags_by_sauce, sources, post.rating = prepare_post(sauce_results, config)
            post.source = collect_sources(*sources, *post.source.splitlines())
        else:
            tags_by_sauce = []
    else:
        tags_by_sauce = []

    # Tag with Deepbooru.
    pixiv_result_only = True if len(tags_by_sauce) < 2 else False
    if (
        (not tags_by_md5 and pixiv_result_only and config.auto_tagger['deepbooru']) or config.auto_tagger['deepbooru_forced']
    ) and post.type != 'video':
        result = deepbooru.tag_image(
            image,
            config.auto_tagger['default_safety'],
            config.auto_tagger['deepbooru_threshold'],
            config.auto_tagger['deepbooru_set_tag'],
        )

        tags_by_deepbooru, post.safety = result

        if tags_by_deepbooru:
            # Deepbooru detects characters, but not the parody.
            # Set the parody based on the character if configured.
            # Only do this if no previous tags where found as this operation takes quite some time
            if not tags_by_md5 and not tags_by_sauce and config.auto_tagger['update_relations']:
                for tag in tags_by_deepbooru:
                    for implication in get_cached_implications(tag, create_missing=True):
                        if implication not in post.tags:
                            post.tags.append(implication)

        if post.relations:
            set_tags_from_relations(post)
    else:
        tags_by_deepbooru = []

    # Keep previous tags and add user tags if configured
    if add_tags:
        tags = list(set().union(post.tags, tags_by_md5, tags_by_sauce, tags_by_deepbooru, add_tags))
    else:
        tags = list(set().union(post.tags, tags_by_md5, tags_by_sauce, tags_by_deepbooru))

    post.tags = [tag for tag in tags if tag is not None]
    sanitize_tags(post.tags)

    if remove_tags:
        [post.tags.remove(tag) for tag in remove_tags if tag in post.tags]

    # If any tags were collected, remove tagme and deepbooru tag
    if tags_by_md5 or tags_by_sauce or tags_by_deepbooru:
        [post.tags.remove(tag) for tag in post.tags if tag == 'tagme']
    else:
        post.tags.append('tagme')

    szuru.update_post(post)

    if tags_by_md5 or tags_by_sauce:
        statistics(tagged=1)

    if tags_by_deepbooru:
        statistics(deepbooru=1)

    if not tags_by_md5 and not tags_by_sauce and not tags_by_deepbooru:
        statistics(untagged=1)


@logger.catch
def main(  # noqa C901
    query: str = '',
    add_tags: list = [],
    remove_tags: list = [],
    post_id: str = None,
    file_to_upload: bytes = None,
    limit_reached: bool = False,
    md5: str = '',
) -> None:
    """
    Automatically tag posts with tags from SauceNAO, Booru posts matching the MD5 hash and/or Deepbooru.

    Posts are processed concurrently by a configurable number of workers
    (`workers` under `[auto_tagger]`).

    This function can be used to auto tag a specific post by supplying the `post_id` of the szurubooru post. It can also
    accept a `file_to_upload` in case the file is already locally available so it doesn't have to get downloaded.

    If called with no arguments, it reads from command line arguments.

    Args:
        query (str, optional): The query to use for retrieving posts. Defaults to ''.
        add_tags (list, optional): Tags to add to the post. Defaults to '[]
        remove_tags (list, optional): Tags to remove from the post. Defaults to [].
        post_id (str, optional): The `post_id` of the szurubooru post. Defaults to None.
        file_to_upload (bytes, optional): If set, will be uploaded to SauceNAO directly. Defaults to None.
        limit_reached (bool, optional): If set, indicates that the SauceNAO limit has been reached. Defaults to False.
        md5 (str, optional): If set, will search boorus with given md5 hash instead of the one from the post. Defaults to ''.

    Returns:
        None
    """

    try:
        # If this script/function was called from the upload-media script,
        # change output and behaviour of this script
        from_upload_media = True if post_id else False

        if from_upload_media:
            hide_progress = True
        else:
            logger.info(f'Retrieving posts from {config.globals["url"]} with query "{query}"...')

        if not config.auto_tagger['saucenao'] and not config.auto_tagger['deepbooru'] and not config.auto_tagger['md5_search']:
            logger.info('Nothing to do. Enable either SauceNAO or Deepbooru in your config.')
            exit()

        # If posts are being tagged directly from upload-media script
        if not from_upload_media:
            try:
                hide_progress = config.globals['hide_progress']
            except KeyError:
                hide_progress = config.auto_tagger['hide_progress']
        else:
            query = post_id

        if config.auto_tagger['saucenao']:
            sauce = SauceNao(config)
        else:
            sauce = None

        if config.auto_tagger['deepbooru']:
            try:
                from szurubooru_toolkit.deepbooru import Deepbooru
            except ImportError:
                logger.critical(
                    'Deepbooru support requires the "deepbooru" extra. Install it with: pip install szurubooru-toolkit[deepbooru]',
                )
                exit(1)
            global deepbooru
            with _deepbooru_lock:
                if deepbooru is None:
                    deepbooru = Deepbooru(config.auto_tagger['deepbooru_model'])

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        if (limit := config.auto_tagger['limit']) and int(limit) > 0 and int(limit) < int(total_posts):
            posts = [next(posts) for _ in range(int(limit))]
            total_posts = len(posts)

        if not from_upload_media:
            logger.info(f'Found {total_posts} posts. Start tagging...')

        if limit_reached:
            _limit_event.set()

        def worker(post: Post) -> None:
            process_post(post, sauce, _cooldown, _limit_event, add_tags, remove_tags, md5, file_to_upload)

        if from_upload_media:
            # Single post handed over from upload-media: process directly
            for post in posts:
                worker(post)

            return _limit_event.is_set()

        workers = max(1, int(config.auto_tagger['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), hide_progress)

        print_statistics(total_posts)
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        try:
            print_statistics(total_posts)
        except UnboundLocalError:
            print_statistics(0)
        exit(1)


if __name__ == '__main__':
    main()
