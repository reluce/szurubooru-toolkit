import argparse
import sys
from time import sleep

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import SauceNao
from szurubooru_toolkit import Szurubooru
from szurubooru_toolkit import config
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import sanitize_tags
from szurubooru_toolkit.utils import scrape_sankaku
from szurubooru_toolkit.utils import statistics


sys.tracebacklimit = 0


def parse_args() -> tuple:
    """
    Parse the input args to the script auto_tagger.py and set the object attributes accordingly.
    """

    parser = argparse.ArgumentParser(
        description='This script will automagically tag your szurubooru posts based on your input query.',
    )

    parser.add_argument(
        '--sankaku_url',
        default=None,
        help='Fetch tags from specified Sankaku URL instead of searching SauceNAO.',
    )
    parser.add_argument(
        'query',
        help='Specify a single post id to tag or a szuru query. E.g. "date:today tag-count:0"',
    )

    parser.add_argument(
        '--add-tags',
        default=None,
        help='Specify tags, separated by a comma, which will be added to all posts matching your query',
    )

    parser.add_argument(
        '--remove-tags',
        default=None,
        help='Specify tags, separated by a comma, which will be removed from all posts matching your query',
    )

    args = parser.parse_args()

    sankaku_url = args.sankaku_url
    logger.debug(f'sankaku_url = {sankaku_url}')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    add_tags = args.add_tags
    logger.debug(f'add_tags = {add_tags}')
    remove_tags = args.remove_tags
    logger.debug(f'remove_tags = {remove_tags}')

    if add_tags:
        add_tags = add_tags.split(',')
    if remove_tags:
        remove_tags = remove_tags.split(',')

    return sankaku_url, query, add_tags, remove_tags


def parse_saucenao_results(sauce: SauceNao, post, config):
    limit_reached = False
    tags, source, rating, limit_short, limit_long = sauce.get_metadata(
        post.content_url,
        config.szurubooru['public'],
        config.auto_tagger['tmp_path'],
    )

    # Get previously set sources and add new sources
    source = collect_sources(*source.splitlines(), *post.source.splitlines())

    if not limit_long == 0:
        # Sleep 35 seconds after short limit has been reached
        if limit_short == 0:
            logger.warning('Short limit reached for SauceNAO, trying again in 35s...')
            sleep(35)
    else:
        limit_reached = True
        logger.info('Your daily SauceNAO limit has been reached. Consider upgrading your account.')

    if tags:
        statistics(tagged=1)

    if limit_reached and config.auto_tagger['deepbooru_enabled']:
        config.auto_tagger['saucenao_enabled'] = False
        logger.info('Continuing tagging with Deepbooru only...')

    return sanitize_tags(tags), source, rating, limit_reached


@logger.catch
def main() -> None:
    """Placeholder"""

    logger.info('Initializing script...')

    if not config.auto_tagger['saucenao_enabled'] and not config.auto_tagger['deepbooru_enabled']:
        logger.info('Nothing to do. Enable either SauceNAO or Deepbooru in your config.')
        exit()

    sankaku_url, query, add_tags, remove_tags = parse_args()

    szuru = Szurubooru(config.szurubooru['url'], config.szurubooru['username'], config.szurubooru['api_token'])

    if config.auto_tagger['saucenao_enabled']:
        sauce = SauceNao(config)

    if config.auto_tagger['deepbooru_enabled']:
        from szurubooru_toolkit import Deepbooru

        deepbooru = Deepbooru(config.auto_tagger['deepbooru_model'])

    logger.info(f'Retrieving posts from {config.szurubooru["url"]} with query "{query}"...')
    posts = szuru.get_posts(query)
    total_posts = next(posts)

    blacklist_extensions = ['mp4', 'webm', 'mkv']

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

            is_blacklisted = False
            for extension in blacklist_extensions:
                if extension in post.content_url:
                    is_blacklisted = True

            if is_blacklisted:
                statistics(skipped=1)
                continue

            if config.auto_tagger['saucenao_enabled']:
                tags, post.source, post.safety, limit_reached = parse_saucenao_results(
                    sauce,
                    post,
                    config,
                )

                if add_tags:
                    post.tags = list(set().union(post.tags, tags, add_tags))  # Keep previous tags, add user tags
                else:
                    post.tags = list(set().union(post.tags, tags))  # Keep previous tags, add user tags

            # if not tags and config.auto_tagger['deepbooru_enabled']:
            if (not tags and config.auto_tagger['deepbooru_enabled']) or config.auto_tagger['deepbooru_forced']:
                tags, post.safety = deepbooru.tag_image(
                    config.auto_tagger['tmp_path'],
                    post.content_url,
                    config.auto_tagger['deepbooru_threshold'],
                )

                # Copy artist, character and series from relations.
                # Useful for FANBOX/Fantia sets where the main post is uploaded to a Booru.
                if post.relations:
                    for relation in post.relations:
                        result = szuru.api.getPost(relation['id'])

                        for relation_tag in result.tags:
                            if not relation_tag.category == 'default' or not relation_tag.category == 'meta':
                                post.tags.append(relation_tag.primary_name)

                if add_tags:
                    post.tags = list(set().union(post.tags, tags, add_tags))  # Keep previous tags, add user tags
                else:
                    post.tags = list(set().union(post.tags, tags))  # Keep previous tags, add user tags

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

            # If any tags were collected with SauceNAO or Deepbooru, tag the post
            if remove_tags:
                [post.tags.remove(tag) for tag in remove_tags if tag in post.tags]

            if tags:
                [post.tags.remove(tag) for tag in post.tags if tag == 'deepbooru' or tag == 'tagme']
                szuru.update_post(post)

            if limit_reached and not config.auto_tagger['deepbooru_enabled']:
                statistics(untagged=int(total_posts) - index - 1)  # Index starts at 0
                break

    total_tagged, total_deepbooru, total_untagged, total_skipped = statistics()

    logger.success('Script has finished tagging.')
    logger.success(f'Total:     {total_posts}')
    logger.success(f'Tagged:    {str(total_tagged)}')
    logger.success(f'Deepbooru: {str(total_deepbooru)}')
    logger.success(f'Untagged:  {str(total_untagged)}')
    logger.success(f'Skipped:   {str(total_skipped)}')


if __name__ == '__main__':
    main()
