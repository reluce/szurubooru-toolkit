from __future__ import annotations

import argparse
from sys import argv
from time import sleep

from loguru import logger
from PIL import UnidentifiedImageError
from tqdm import tqdm

from szurubooru_toolkit import Post
from szurubooru_toolkit import SauceNao
from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import sanitize_tags
from szurubooru_toolkit.utils import scrape_sankaku
from szurubooru_toolkit.utils import shrink_img
from szurubooru_toolkit.utils import statistics


def parse_args() -> tuple:
    """Parse the input args to the script auto_tagger.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will automagically tag your szurubooru posts based on your input query.',
    )

    parser.add_argument(
        '--sankaku-url',
        default=None,
        help='Fetch tags from specified Sankaku URL instead of searching SauceNAO.',
    )

    parser.add_argument(
        '--add-tags',
        default=None,
        help='Specify tags, separated by a comma, which will be added to all posts matching your query.',
    )

    parser.add_argument(
        '--remove-tags',
        default=None,
        help='Specify tags, separated by a comma, which will be removed from all posts matching your query.',
    )

    parser.add_argument(
        'query',
        help='Specify a single post id to tag or a szuru query. E.g. "date:today tag-count:0"',
    )

    # Don't parse the query (should be latest arg), as it might contain a dash (-) to negative the search token
    # Otherwise, parse_args() would interpret it as an argument
    # args.query results in the script name, but we use argv[-1] to extract the query
    # As -h won't get interpreted with this approach, we have to implement it manually
    if any(help_str in ['-h', '-help', '--help'] for help_str in argv):
        parser.print_help()
        exit()
    args = parser.parse_args(argv[:-1])
    query = argv[-1]

    sankaku_url = args.sankaku_url
    logger.debug(f'sankaku_url = {sankaku_url}')

    logger.debug(f'query = {query}')

    if 'type:' in query:
        logger.critical('Search token "type" is not allowed in queries!')
        exit()

    if '\'' in query:
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    add_tags = args.add_tags
    remove_tags = args.remove_tags

    if add_tags:
        logger.debug(f'add_tags = {add_tags}')
        add_tags = add_tags.replace(' ', '').split(',')
    if remove_tags:
        remove_tags = remove_tags.replace(' ', '').split(',')
        logger.debug(f'remove_tags = {remove_tags}')

    return sankaku_url, query, add_tags, remove_tags


def parse_saucenao_results(sauce: SauceNao, post: Post, image: bytes) -> tuple[list, str, str, bool]:
    """Retrieve and parse result from SauceNAO with the `image` to be uploaded.

    Args:
        sauce (SauceNao): SauceNao object.
        post (Post): szurubooru Post object.
        image (bytes): The image to uploade to upload to SauceNAO.

    Returns:
        tuple[list, str, str, bool]: List of tags, the source, rating and if the SauceNAO limit has been reached.
    """

    limit_reached = False
    tags, source, rating, limit_short, limit_long = sauce.get_metadata(post.content_url, image)

    # Get previously set sources and add new sources
    source = collect_sources(*source.splitlines(), *post.source.splitlines())

    if not limit_long == 0:
        # Sleep 35 seconds after short limit has been reached
        if limit_short == 0:
            print('')
            logger.debug('Short limit reached for SauceNAO, trying again in 35s...')
            sleep(35)
    else:
        limit_reached = True
        print('')
        logger.info('Your daily SauceNAO limit has been reached. Consider upgrading your account.')

    if tags:
        statistics(tagged=1)

    if limit_reached and config.auto_tagger['deepbooru_enabled']:
        config.auto_tagger['saucenao_enabled'] = False
        logger.info('Continuing tagging with Deepbooru only...')

    return sanitize_tags(tags), source, rating, limit_reached


def set_tags_from_relations(post: Post) -> None:
    """Copy artist, character and series from relations.

    Useful for FANBOX/Fantia sets where only the main post is uploaded to a Booru.

    Args:
        post (Post): szurubooru Post object.
    """

    for relation in post.relations:
        result = szuru.api.getPost(relation['id'])

        for relation_tag in result.tags:
            if not relation_tag.category == 'default' or not relation_tag.category == 'meta':
                post.tags.append(relation_tag.primary_name)


@logger.catch
def main(post_id: str = None, file_to_upload: bytes = None) -> None:  # noqa C901
    """Automatically tag posts with SauceNAO and/or Deepbooru.

    To auto tag a specific post, supply the `post_id` of the szurubooru post.
    You can also provide `file_to_upload` in case the file is already locally available so
    it doesn't have to get downloaded.

    If called with no arguments, read from command line arguments.

    Args:
        post_id (str, optional): The `post_id` of the szurubooru post. Defaults to None.
        file_to_upload (bytes, optional): If set, will be uploaded to SauceNAO directly. Defaults to None.
    """

    try:
        # If this script/function was called from the upload-media script,
        # change output and behaviour of this script
        from_upload_media = True if post_id else False

        if not from_upload_media:
            logger.info('Initializing script...')
        else:
            config.auto_tagger['hide_progress'] = True

        if not config.auto_tagger['saucenao_enabled'] and not config.auto_tagger['deepbooru_enabled']:
            logger.info('Nothing to do. Enable either SauceNAO or Deepbooru in your config.')
            exit()

        # If posts are being tagged directly from upload-media script
        if not from_upload_media:
            sankaku_url, query, add_tags, remove_tags = parse_args()
        else:
            sankaku_url = None
            query = post_id
            add_tags = None
            remove_tags = None

        if config.auto_tagger['saucenao_enabled']:
            sauce = SauceNao(config)

        if config.auto_tagger['deepbooru_enabled']:
            from szurubooru_toolkit import Deepbooru

            deepbooru = Deepbooru(config.auto_tagger['deepbooru_model'])

        if not from_upload_media:
            logger.info(f'Retrieving posts from {config.szurubooru["url"]} with query "{query}"...')

        posts = szuru.get_posts(query)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        if not from_upload_media:
            logger.info(f'Found {total_posts} posts. Start tagging...')

        if sankaku_url:
            if query.isnumeric():
                post = next(posts)
                post.tags, post.safety = scrape_sankaku(sankaku_url)
                post.source = sankaku_url

                try:
                    szuru.update_post(post)
                    statistics(tagged=1)
                except Exception as e:
                    statistics(untagged=1)
                    logger.error(f'Could not tag post with Sankaku: {e}')
            else:
                logger.critical('Can only tag a single post if you specify --sankaku_url.')
        else:
            for index, post in enumerate(
                tqdm(
                    posts,
                    ncols=80,
                    position=0,
                    leave=False,
                    disable=config.auto_tagger['hide_progress'],
                    total=int(total_posts),
                ),
            ):
                tags = []

                # Download the file from szurubooru if its not already locally present.
                # This might be the case if this function was called from upload_media.
                if not file_to_upload:
                    if not config.szurubooru['public'] or config.auto_tagger['deepbooru_enabled']:
                        image = download_media(post.content_url, post.md5)
                        # Shrink files >2MB
                        try:
                            if len(image) > 2000000:
                                image = shrink_img(image, resize=True, convert=True)
                        except UnidentifiedImageError:
                            logger.warning('Could not shrink image')
                    else:
                        image = None  # Let SauceNAO download the image from public szurubooru URL
                else:
                    image = file_to_upload

                if config.auto_tagger['saucenao_enabled']:
                    tags, post.source, post.safety, limit_reached = parse_saucenao_results(
                        sauce,
                        post,
                        image,
                    )

                    if add_tags:
                        post.tags = list(set().union(post.tags, tags, add_tags))  # Keep previous tags, add user tags
                    else:
                        post.tags = list(set().union(post.tags, tags))  # Keep previous tags, add user tags
                else:
                    limit_reached = False

                if (not tags and config.auto_tagger['deepbooru_enabled']) or config.auto_tagger['deepbooru_forced']:
                    result = deepbooru.tag_image(
                        image,
                        config.auto_tagger['deepbooru_threshold'],
                        config.auto_tagger['deepbooru_set_tag'],
                    )

                    if result is None:
                        continue

                    tags, post.safety = result

                    if post.relations:
                        set_tags_from_relations(post)

                    if add_tags:
                        post.tags = list(set().union(post.tags, tags, add_tags))  # Keep previous tags and add user tags
                    else:
                        post.tags = list(set().union(post.tags, tags))  # Keep previous tags

                    if 'DeepBooru' in post.source:
                        post.source = post.source.replace('DeepBooru\n', '')
                        post.source = post.source.replace('\nDeepBooru', '')

                    if 'Deepbooru' not in post.source:
                        post.source = collect_sources(post.source, 'Deepbooru')

                    if tags:
                        statistics(deepbooru=1)
                    else:
                        statistics(untagged=1)
                elif not tags:
                    statistics(untagged=1)

                if remove_tags:
                    [post.tags.remove(tag) for tag in remove_tags if tag in post.tags]

                # If any tags were collected with SauceNAO or Deepbooru, remove tagme and deepbooru tag
                if tags:
                    [post.tags.remove(tag) for tag in post.tags if tag == 'tagme']
                else:
                    post.tags.append('tagme')

                szuru.update_post(post)

                if limit_reached and not config.auto_tagger['deepbooru_enabled']:
                    statistics(untagged=int(total_posts) - index - 1)  # Index starts at 0
                    break

        if not from_upload_media:
            total_tagged, total_deepbooru, total_untagged, total_skipped = statistics()

            logger.success('Script has finished tagging.')
            logger.success(f'Total:     {total_posts}')
            logger.success(f'Tagged:    {str(total_tagged)}')
            logger.success(f'Deepbooru: {str(total_deepbooru)}')
            logger.success(f'Untagged:  {str(total_untagged)}')
            logger.success(f'Skipped:   {str(total_skipped)}')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
