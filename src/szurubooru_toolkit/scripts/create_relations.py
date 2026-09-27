import threading

from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import UnknownTokenError
from szurubooru_toolkit.utils import interrupt_exit
from szurubooru_toolkit.utils import run_concurrently

# Workers count posts concurrently; the tag updates are serialized, since two relations
# of the same tag pushed at once would conflict on the tag version
_update_lock = threading.Lock()
_found_lock = threading.Lock()


def collect_related_tags(tags: list[Tag]) -> list[Tag]:
    """
    Collect all character and parody tags from a tag list.

    This function iterates over a list of szurubooru Tag objects and adds any tag whose category is 'character', 'parody',
    or 'series' to a new list. It then returns this new list.

    Args:
        tags (list[Tag]): A list of szurubooru Tag objects to process.

    Returns:
        list[Tag]: A list of szurubooru Tag objects whose category is 'character', 'parody', or 'series'.
    """

    related_tags = []

    for tag in tags:
        if tag.category in ['character', 'parody', 'series']:
            related_tags.append(tag)

    return related_tags


def update_tag(tag: Tag, relation: Tag) -> None:
    """
    Updates the implications or suggestions of a tag based on a related tag.

    This function checks the category of the provided tag and the related tag. If the tag is a character tag and the
    related tag is a parody or series tag, it adds the related tag as an implication for the tag. If the tag is a parody
    or series tag and the related tag is a character tag, it adds the related tag as a suggestion for the tag.

    The function only adds the related tag as an implication or suggestion if it's not already present in the tag's
    implications or suggestions. After adding the related tag, it pushes the changes to szurubooru.

    Args:
        tag (Tag): A szurubooru Tag object to update (micro tag, gets fetched in full before updating).
        relation (Tag): A szurubooru Tag object that is related to the tag.

    Returns:
        None
    """

    if tag.category == 'character' and relation.category in ['parody', 'series']:
        target_list = 'implications'
    elif tag.category in ['parody', 'series'] and relation.category == 'character':
        target_list = 'suggestions'
    else:
        return

    # Micro tags don't carry implications/suggestions, so fetch the full tag before updating
    full_tag = szuru.get_tag(tag.primary_name)
    existing = getattr(full_tag, target_list)

    if relation.primary_name not in [entry.primary_name for entry in existing]:
        existing.append(relation)
        szuru.update_tag(full_tag)


def is_relatable(tag: Tag, relation: Tag) -> bool:
    """Only character <> parody/series pairs get related."""

    return (tag.category == 'character' and relation.category in ['parody', 'series']) or (
        tag.category in ['parody', 'series'] and relation.category == 'character'
    )


def evaluate_relations(tag: Tag, relation: Tag) -> None:
    """
    Evaluates if the relation between two tags is valid and updates the tag if so.

    This function checks the possible relation of two tags on szurubooru. If the count of search results reaches the
    configured threshold, the relation is considered valid.

    Args:
        tag (Tag): A szurubooru Tag object.
        relation (Tag): A szurubooru Tag object with a possible relation to `tag`.

    Returns:
        None
    """

    # Create the relation only if at least the configured threshold of posts has both tags
    try:
        # Only the total is needed, so ask for a single post
        count = next(szuru.get_posts(f'{tag.primary_name} {relation.primary_name}', max_results=1))
    except StopIteration:
        count = 0

    if int(count) >= int(config.create_relations['threshold']):
        with _update_lock:
            update_tag(tag, relation)


def check_found_relations(related_tags: list[Tag], found_relations: dict) -> None:
    """
    Evaluates every relatable pair in related_tags which hasn't been evaluated yet.

    Each direction of a pair is evaluated once per run: the character gets the parody as implication, the parody gets
    the character as suggestion. The post count is global, so evaluating a pair again can't change the result.

    Args:
        related_tags (list[Tag]): List of tag objects where category is either character or parody.
        found_relations (dict): Dictionary which keeps track of already evaluated relations. The key is the tag's name
                                while its value is a set of evaluated relations.

    Returns:
        None
    """

    for tag in related_tags:
        for relation in related_tags:
            if not is_relatable(tag, relation):
                continue

            with _found_lock:
                evaluated = found_relations.setdefault(tag.primary_name, set())
                if relation.primary_name in evaluated:
                    continue
                evaluated.add(relation.primary_name)

            try:
                evaluate_relations(tag, relation)
            # Skip tags szurubooru cannot search for, e.g. tags with unescaped special chars
            except SzurubooruError as e:
                logger.debug(f'Skipping relation {tag.primary_name} <> {relation.primary_name}: {e}')


@logger.catch
def main(query: str) -> None:
    """
    Create relations between character and parody tag categories.

    Parody will be added as an implication to characters while characters will be added as suggestions to parodies.

    Args:
        query (str): The query to use for retrieving posts.

    Returns:
        None
    """

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.create_relations['hide_progress']

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()
        except UnknownTokenError as e:
            logger.critical(f'Could not process your query: {e}')
            exit(1)

        logger.info(f'Found {total_posts} posts. Start generating relations...')

        # Keep track of found relations to reduce overhead
        found_relations = {}

        def worker(post) -> None:
            check_found_relations(collect_related_tags(post.micro_tags), found_relations)

        workers = max(1, int(config.create_relations['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), hide_progress)

        logger.success('Finished creating relations!')
        exit(0)
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        interrupt_exit()


if __name__ == '__main__':
    main()
