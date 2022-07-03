import argparse

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru


def parse_args() -> tuple:
    """Parse the input args to the script tag_posts.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will tag your szurubooru posts based on your input arguments and mode.',
    )

    parser.add_argument(
        '--add-tags',
        type=str,
        default=None,
        help='Specify tags, separated by a comma, which will be added to all posts matching your query.',
    )

    parser.add_argument(
        '--remove-tags',
        type=str,
        default=None,
        help='Specify tags, separated by a comma, which will be removed from all posts matching your query.',
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['append', 'overwrite'],
        default='append',
        help='Set mode to overwrite to remove already set tags, set append to keep them (default: append).',
    )

    parser.add_argument(
        'query',
        help='The search query for the posts you want to tag',
    )

    args = parser.parse_args()

    add_tags = args.add_tags
    logger.debug(f'add_tags = {add_tags}')
    remove_tags = args.remove_tags
    logger.debug(f'remove_tags = {remove_tags}')

    if not add_tags and not remove_tags:
        logger.critical('You have to specify either --add-tags or --remove-tags as an argument!')
        exit()

    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
    if remove_tags:
        remove_tags = remove_tags.replace(' ', '').split(',')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        print('')
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return add_tags, remove_tags, args.mode, query


@logger.catch
def main() -> None:
    """Retrieve the posts from input query, set post.tags based on mode and update them in szurubooru."""

    add_tags, remove_tags, mode, query = parse_args()

    posts = szuru.get_posts(query)

    try:
        total_posts = next(posts)
    except StopIteration:
        logger.info(f'Found no posts for your query: {query}')
        exit()

    logger.info(f'Found {total_posts} posts. Start tagging...')

    for post in tqdm(
        posts,
        ncols=80,
        position=0,
        leave=False,
        total=int(total_posts),
        disable=config.tag_posts['hide_progress'],
    ):
        if mode == 'append':
            if add_tags:
                post.tags = list(set().union(post.tags, add_tags))
        elif mode == 'overwrite':
            if add_tags:
                post.tags = add_tags

        if remove_tags:
            post.tags = [tag for tag in post.tags if tag not in remove_tags]

        szuru.update_post(post)

    logger.success('Script finished tagging!')


if __name__ == '__main__':
    main()
