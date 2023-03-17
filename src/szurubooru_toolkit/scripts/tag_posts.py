import argparse
from sys import argv

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
        '--update-implications',
        action='store_true',
        default=False,
        help='Fetches all tags from the posts matching the query and updates them if tag implications are \
            missing (default: False)',
    )

    parser.add_argument(
        'query',
        help='The search query for the posts you want to tag.',
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

    add_tags = args.add_tags
    logger.debug(f'add_tags = {add_tags}')
    remove_tags = args.remove_tags
    logger.debug(f'remove_tags = {remove_tags}')

    update_implications = args.update_implications
    logger.debug(f'update_implications = {str(update_implications)}')

    if not add_tags and not remove_tags and not update_implications:
        logger.critical('You have to specify either --add-tags, --remove-tags or --update-implications as an argument!')
        exit()

    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
    if remove_tags:
        remove_tags = remove_tags.replace(' ', '').split(',')

    logger.debug(f'query = {query}')
    if '\'' in query:
        print('')
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return add_tags, remove_tags, update_implications, args.mode, query


@logger.catch
def main() -> None:
    """Retrieve the posts from input query, set post.tags based on mode and update them in szurubooru."""

    try:
        add_tags, remove_tags, update_implications, mode, query = parse_args()

        posts = szuru.get_posts(query, videos=True)

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

            if update_implications:
                for tag in post.tags:
                    szuru_tag = szuru.api.getTag(tag)
                    for implication in szuru_tag.implications:
                        szuru_implication = szuru.api.getTag(implication)
                        if szuru_implication not in post.tags:
                            post.tags.append(szuru_implication.primary_name)

            szuru.update_post(post)

        logger.success('Script finished tagging!')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
