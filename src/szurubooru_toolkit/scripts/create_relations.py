import argparse

from loguru import logger
from pyszuru.api import SzurubooruHTTPError
from tqdm import tqdm

from szurubooru_toolkit import szuru


def parse_args() -> tuple:
    """Parse the input args to the script create_relations.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='Create relations between character and parody tag categories',
    )

    parser.add_argument(
        '--hide-progress',
        default=False,
        help='Hide the progress bar.',
    )

    parser.add_argument(
        'query',
        default='*',
        help='Search for specific tags (default: "*").',
    )
    args = parser.parse_args()

    return args.query, args.hide_progress


@logger.catch
def main() -> None:
    """Create relations between character and parody tag categories.

    Parody will be added as an implication to characters while characters will be added as suggestions to parodies.
    """

    try:
        query, hide_progress = parse_args()
        # Use this method to only retrieve the total amount of posts.
        # Otherwise using szuru.api.search_post(query), we would have to use len(list(<generator>)),
        # which would take too much time (and also consume the generator).
        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Start generating implications...')

        # Use this method to get the tag objects already included
        posts = szuru.api.search_post(query)

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
            related_tags = []

            for tag in post.tags:
                if tag.category in ['character', 'parody', 'series']:
                    related_tags.append(tag)

            for tag in related_tags:
                implications = [implication for implication in related_tags if implication is not tag]
                for implication in implications:
                    try:
                        # Add parody/series tag as an implication for character tags
                        if tag.category == 'character' and implication.category in ['parody', 'series']:
                            # Somehow tag.implications.append(implication) does not work
                            tag.implications = tag.implications + [implication]
                            # Make list unique
                            tag.implications = list(set(tag.implications))
                        # Add character tags as a suggestion to parody/series tags
                        elif tag.category in ['parody', 'series'] and implication.category == 'character':
                            tag.suggestions = tag.suggestions + [implication]
                            tag.suggestions = list(set(tag.suggestions))
                        tag.push()
                    # This exception gets thrown sometimes if 'name' is not set.
                    # I could not pinpoint what this 'name' was referencing and it still worked, so we just ignore it.
                    except SzurubooruHTTPError:
                        pass

        logger.success('Script finished creating relations!')
        exit(0)
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
