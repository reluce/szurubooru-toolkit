import argparse
from sys import argv

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru


def parse_args() -> tuple:
    """Parse the input args to the script reset_posts.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will remove tags and sources from your szurubooru posts \
            based on your input search query.',
    )

    parser.add_argument(
        '--except-ids',
        default=[],
        help='Specify the post ids, separated by a comma, which should not be reset. \
            Example: --except-ids "3,4,5"',
    )

    parser.add_argument(
        '--add-tags',
        default=[],
        help='Specify tags, separated by a comma, which will be added to all posts \
            matching your query after resetting.',
    )

    parser.add_argument(
        'query',
        help='The search query for the posts you want to reset.',
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

    add_tags = args.add_tags
    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
        logger.debug(f'add_tags = {add_tags}')

    logger.debug(f'query = {query}')
    if '\'' in query:
        print('')
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return add_tags, except_ids, query


@logger.catch
def main() -> None:
    """Retrieve the posts from input query and reset them in szurubooru."""

    try:
        add_tags, except_ids, query = parse_args()

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Start resetting...')
        if except_ids:
            logger.info(f'Won\'t reset the following ids: {except_ids}')

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=config.reset_posts['hide_progress'],
        ):
            if post.id not in except_ids:
                post.tags = add_tags if add_tags else []
                post.source = ''
                szuru.update_post(post)

        logger.success('Script finished resetting!')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
