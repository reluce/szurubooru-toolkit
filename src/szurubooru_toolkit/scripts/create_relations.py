import argparse

from loguru import logger
from pyszuru import Tag
from pyszuru.api import SzurubooruHTTPError
from tqdm import tqdm

from szurubooru_toolkit import config
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


def collect_related_tags(tags: list[Tag]) -> list[Tag]:
    """Collect all character and parody tags from a tag list.

    Args:
        tags (list): List with tag objects.

    Returns:
        related_tags (list[Tag]): List of tag objects where category is either character or parody.
    """

    related_tags = []

    for tag in tags:
        if tag.category in ['character', 'parody', 'series']:
            related_tags.append(tag)

    return related_tags


def update_tag(tag: Tag, relation: Tag) -> None:
    """Update the tags implications or suggestions.

    The update will only be pushed if the relation is not already present in the tag itself.

    Args:
        tag (Tag): Szurubooru tag object
        relation (Tag): Szurubooru tag object with relation to tag

    Returns:
        None
    """

    # Add parody/series tag as an implication for character tags
    if tag.category == 'character' and relation.category in ['parody', 'series']:
        if relation.primary_name not in [implication.primary_name for implication in tag.implications]:
            tag.implications.append(relation)
            tag.push()
    # Add character tags as a suggestion to parody/series tags
    elif tag.category in ['parody', 'series'] and relation.category == 'character':
        if relation.primary_name not in [suggestion.primary_name for suggestion in tag.suggestions]:
            tag.suggestions.append(relation)
            tag.push()


def evaluate_relations(tag: Tag, relation: Tag, found_relations: dict) -> None:
    """Evaluate if the tag relation is valid.

    This is done by searching the possible relation of two tags on szurubooru.
    If the count of search results is above the configured threshold, the relation is valid.

    Also check relation against found_relations. Update the tag with the new relation only
    if the relation was not already set before.

    Args:
        tag (Tag): Szurubooru tag object
        relation (Tag): Szurubooru tag object with possible relation to tag
        found_relations (dict): Dictionary which keeps track of already matched relations.
            The key is the tags name while its value is a list of matched relations.

    Returns:
        None
    """

    # Create relation only if count of existing relation is above configured threshold
    try:
        count = next(szuru.get_posts(f'{tag.primary_name} {relation.primary_name}'))
    except StopIteration:
        count = 0

    if int(count) > int(config.create_relations['threshold']):
        # Update found_relations
        if tag.primary_name not in found_relations:
            found_relations[tag.primary_name] = []

        if relation.primary_name not in found_relations[tag.primary_name]:
            # Match only character and parody/series
            if (tag.category == 'character' and relation.category in ['parody', 'series']) or (
                tag.category in ['parody', 'series'] and relation.category == 'character'
            ):
                found_relations[tag.primary_name].append(relation.primary_name)

            update_tag(tag, relation)


def check_found_relations(related_tags: list[Tag], found_relations: dict) -> None:
    """Check each tag in related_tags if it's been matched already in found_relations.

    If not, continue to update it's relation.

    Args:
        related_tags (list[Tag]):  List of tag objects where category is either character or parody.
        found_relations (dict): Dictionary which keeps track of already matched relations.
            The key is the tags name while its value is a list of matched relations.

    Returns:
        None
    """

    for tag in related_tags:
        # relations doesn't include the current tag
        relations = related_tags.copy()
        relations.remove(tag)

        for relation in relations:
            try:
                if relation.primary_name not in found_relations:
                    evaluate_relations(tag, relation, found_relations)
            # This exception gets thrown sometimes if 'name' is not set.
            # I could not pinpoint what this 'name' was referencing and it still worked, so we just ignore it.
            except SzurubooruHTTPError:
                pass


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

        logger.info(f'Found {total_posts} posts. Start generating relations...')

        # Use this method to get the tag objects already included
        posts = szuru.api.search_post(query)

        # Keep track of found relations to reduce overhead
        found_relations = {}

        # Skip posts with unescaped chars in tag.
        # Wrap it so we can catch the exception within the loop.
        def wrapper(gen):
            while True:
                try:
                    yield next(gen)
                except StopIteration:
                    break
                except SzurubooruHTTPError as e:
                    if 'SearchError: Unknown named token' in str(e):
                        print('')
                        logger.warning(f'Skipping tag: {str(e)}')
                        continue

        for post in tqdm(
            wrapper(posts),
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
            related_tags = collect_related_tags(post.tags)
            check_found_relations(related_tags, found_relations)

        logger.success('Script finished creating relations!')
        exit(0)
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
