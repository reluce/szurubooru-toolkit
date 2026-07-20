from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import TagExistsError
from szurubooru_toolkit.szurubooru import TagNotFoundError


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
            szuru.create_tag(implied, category)

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

        if tag_file:
            with open(tag_file) as tag_file:
                lines = tag_file.readlines()

                for line in tqdm(
                    lines,
                    ncols=80,
                    position=0,
                    leave=False,
                    disable=hide_progress,
                ):
                    tag: list = line.strip().replace(' ', '').split(',')
                    tag_name = tag[0]
                    tag_category = tag[1]

                    try:
                        szuru.create_tag(tag_name, tag_category)
                    except TagExistsError as e:  # noqa F841
                        # logger.warning(e)  # Could result in lots of output with larger tag files
                        pass

                    tag_implications = [implied for implied in tag[2:] if implied]
                    if tag_implications:
                        add_implications(tag_name, tag_implications)
        elif tag_name:
            try:
                szuru.create_tag(tag_name, category or 'default', overwrite)
            except TagExistsError as e:  # noqa F841
                pass

            if implications:
                add_implications(tag_name, implications)
        else:
            from szurubooru_toolkit import danbooru

            results = danbooru.download_tags(config.create_tags['query'], min_post_count, limit)

            for result in results:
                created = []
                for tag in result:
                    if not isinstance(tag, dict) or 'name' not in tag:
                        continue
                    tag_category = convert_tag_category(tag.get('category'))
                    if tag_category is None:
                        continue
                    try:
                        szuru.create_tag(tag['name'], tag_category, overwrite)
                    except TagExistsError as e:  # noqa F841
                        pass
                    created.append(tag['name'])

                if created and config.create_tags['import_implications']:
                    implication_map = danbooru.get_tag_implications(created)
                    consequents = {implied for values in implication_map.values() for implied in values}
                    implied_categories = {
                        name: convert_tag_category(numerical_category) or 'default'
                        for name, numerical_category in danbooru.get_tag_categories(sorted(consequents)).items()
                    }

                    for antecedent, implied_tags in implication_map.items():
                        add_implications(antecedent, implied_tags, implied_categories)

        logger.success('Finished creating tags!')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
