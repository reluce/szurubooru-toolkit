import argparse

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru


def parse_args() -> tuple:
    """Parse the input args to the script delete_posts.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will delete your szurubooru posts based on your input search query.',
    )

    parser.add_argument(
        '--except-ids',
        default=[],
        help='Specify the post ids, separated by a comma, which should not be deleted. Example: --except-ids "3,4,5"',
    )

    parser.add_argument(
        'query',
        help='The search query for the posts you want to delete.',
    )

    args = parser.parse_args()

    except_ids = args.except_ids
    if except_ids:
        except_ids = except_ids.replace(' ', '').split(',')
        logger.debug(f'except_ids = {except_ids}')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        print('')
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return except_ids, query


@logger.catch
def main() -> None:
    """Retrieve the posts from input query and delete them in szurubooru."""

    except_ids, query = parse_args()

    posts = szuru.get_posts(query, pagination=False)

    try:
        total_posts = next(posts)
    except StopIteration:
        logger.info(f'Found no posts for your query: {query}')
        exit()

    logger.info(f'Found {total_posts} posts. Start deleting...')
    if except_ids:
        logger.info(f'Won\'t delete the following ids: {except_ids}')

    for post in tqdm(
        posts,
        ncols=80,
        position=0,
        leave=False,
        total=int(total_posts),
        disable=config.delete_posts['hide_progress'],
    ):
        if post.id not in except_ids:
            szuru.delete_post(post)

    logger.success('Script finished deleting!')


if __name__ == '__main__':
    main()
