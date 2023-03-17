import argparse
from sys import argv

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru


def parse_args() -> tuple:
    """Parse the input args to the script delete_posts.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will delete your szurubooru posts based on your input search query.',
        add_help=False,
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

    # Don't parse the query (should be latest arg), as it might contain a dash (-) to negative the search token
    # Otherwise, parse_args() would interpret it as an argument
    # args.query results in the script name, but we use argv[-1] to extract the query
    # As -h won't get interpreted with this approach, we have to implement it manually
    if any(help_str in ['-h', '-help', '--help'] for help_str in argv):
        parser.print_help()
        exit()
    args = parser.parse_args(argv[:-1])
    query = argv[-1]

    except_ids = args.except_ids
    if except_ids:
        except_ids = except_ids.replace(' ', '').split(',')
        logger.debug(f'except_ids = {except_ids}')

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

    try:
        except_ids, query = parse_args()

        posts = szuru.get_posts(query, pagination=False, videos=True)

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
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
