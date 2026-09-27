from pathlib import Path

from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import TagExistsError
from szurubooru_toolkit.szurubooru import TagNotFoundError
from szurubooru_toolkit.utils import interrupt_exit
from szurubooru_toolkit.utils import run_concurrently


def convert_tag_category(category: int) -> str:
    """
    Converts a numerical category into a string representation.

    This function uses a dictionary to map numerical categories to their string representations. It then returns the
    string representation of the provided category.

    Args:
        category (int): The numerical category to convert.

    Returns:
        str: The string representation of the category.
    """

    switch = {
        0: 'default',
        1: 'artist',
        3: 'series',
        4: 'character',
        5: 'meta',
    }

    category = switch.get(category)

    return category


def add_implications(tag_name: str, implications: list, implied_categories: dict = None) -> None:
    """
    Adds implications to a tag, creating implied tags that don't exist yet.

    Existing implications of the tag are kept; new ones are merged in.

    Args:
        tag_name (str): The tag which implies the others.
        implications (list): The names of the implied tags.
        implied_categories (dict, optional): Categories for implied tags that have to be
                                             created, as {name: category}. Defaults to 'default'.

    Returns:
        None
    """

    for implied in implications:
        try:
            szuru.get_tag(implied)
        except TagNotFoundError:
            category = (implied_categories or {}).get(implied, 'default')
            try:
                szuru.create_tag(implied, category)
            except TagExistsError:
                pass  # Another worker created it in the meantime

    tag = szuru.get_tag(tag_name)
    existing = {implication.primary_name for implication in tag.implications}
    new = [implied for implied in implications if implied not in existing]

    if new:
        tag.implications += [Tag(names=[implied]) for implied in new]
        szuru.update_tag(tag)
        logger.debug(f'Added implications {new} to tag "{tag_name}"')


@logger.catch
def main(tag_file: str = '', tag_name: str = '', category: str = '', implications: list = []) -> None:
    """
    Create tags in szurubooru from a file, a single tag given on the command line, or a Danbooru query.

    A tag file contains one 'name,category' pair per line; any further columns are added as
    implications. A single tag is created from `tag_name`, `category` and `implications`. Without
    either, tags are downloaded from Danbooru based on the configured query, optionally with
    their Danbooru implications (import_implications).

    Args:
        tag_file (str, optional): The path to the file containing the tags to create. Defaults to ''.
        tag_name (str, optional): A single tag to create. Defaults to ''.
        category (str, optional): The category of `tag_name`. Defaults to 'default'.
        implications (list, optional): Tags which `tag_name` implies. Defaults to [].

    Returns:
        None
    """

    try:
        if tag_file:
            tag_file = Path(tag_file)

        min_post_count = int(config.create_tags['min_post_count'])
        limit = int(config.create_tags['limit'])
        overwrite = config.create_tags['overwrite']

        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.create_tags['hide_progress']

        workers = max(1, int(config.create_tags['workers']))

        def create(name: str, tag_category: str) -> None:
            try:
                szuru.create_tag(name, tag_category, overwrite)
            except TagExistsError:
                pass  # Not logged, could result in lots of output with larger tag files

        if tag_file:
            with open(tag_file) as tag_file:
                rows = [line.strip().replace(' ', '').split(',') for line in tag_file]
            rows = [row for row in rows if row[0]]  # skip blank lines

            # Create every tag first, so implied tags defined elsewhere in the file keep their category
            # A line without a category gets the default one
            run_concurrently(
                rows,
                lambda row: create(row[0], row[1] if len(row) > 1 and row[1] else 'default'),
                workers,
                len(rows),
                hide_progress,
            )

            rows = [row for row in rows if any(row[2:])]
            run_concurrently(
                rows,
                lambda row: add_implications(row[0], [implied for implied in row[2:] if implied]),
                workers,
                len(rows),
                True,
            )
        elif tag_name:
            create(tag_name, category or 'default')

            if implications:
                add_implications(tag_name, implications)
        else:
            from szurubooru_toolkit import danbooru

            results = danbooru.download_tags(config.create_tags['query'], min_post_count, limit)

            for result in results:
                page = [
                    (tag['name'], tag_category)
                    for tag in result
                    if isinstance(tag, dict) and 'name' in tag and (tag_category := convert_tag_category(tag.get('category')))
                ]
                run_concurrently(page, lambda entry: create(*entry), workers, len(page), hide_progress)
                created = [name for name, _ in page]

                if created and config.create_tags['import_implications']:
                    implication_map = danbooru.get_tag_implications(created)
                    consequents = {implied for values in implication_map.values() for implied in values}
                    implied_categories = {
                        name: convert_tag_category(numerical_category) or 'default'
                        for name, numerical_category in danbooru.get_tag_categories(sorted(consequents)).items()
                    }

                    run_concurrently(
                        implication_map.items(),
                        lambda entry: add_implications(*entry, implied_categories),
                        workers,
                        len(implication_map),
                        hide_progress,
                    )

        logger.success('Finished creating tags!')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        interrupt_exit()


if __name__ == '__main__':
    main()
