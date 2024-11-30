from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import TagExistsError


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


@logger.catch
def main(tag_file: str = '') -> None:
    """
    Read tags from file or based on a Danbooru query and create them in szurubooru.

    This function reads tags from a file and creates them in szurubooru. It also handles configuration settings such as
    minimum post count, limit, overwrite, and hide progress.

    Args:
        tag_file (str, optional): The path to the file containing the tags to create. Defaults to ''.
        query (str, optional): The query to use for retrieving posts. Defaults to '*'.

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
        else:
            from szurubooru_toolkit import danbooru

            results = danbooru.download_tags(config.create_tags['query'], min_post_count, limit)

            for result in results:
                for tag in result:
                    try:
                        szuru.create_tag(tag['name'], convert_tag_category(tag['category']), overwrite)
                    except TagExistsError as e:  # noqa F841
                        pass

        logger.success('Finished creating tags!')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
