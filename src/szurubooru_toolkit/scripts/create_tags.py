import argparse
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import TagExistsError


def parse_args() -> Path:
    """Parse the input args to the script create_tags.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will read the tags from specified file and create them in your szurubooru.',
    )

    parser.add_argument(
        '--tag-file',
        default=Path('./misc/tags/tags.txt'),
        help='Specify the local path to the file containing the tags and categories \
            (default: ./misc/tags/tags.txt).',
    )

    args = parser.parse_args()

    return Path(args.tag_file)


@logger.catch
def main() -> None:
    """Read tags from file and create them in szurubooru."""

    tags_file = parse_args()

    with open(tags_file) as tags_file:
        lines = tags_file.readlines()

        for line in tqdm(
            lines,
            ncols=80,
            position=0,
            leave=False,
            disable=config.create_tags['hide_progress'],
        ):
            tag: list = line.strip().replace(' ', '').split(',')
            tag_name = tag[0]
            tag_category = tag[1]

            try:
                szuru.create_tag(tag_name, tag_category)
            except TagExistsError as e:  # noqa F841
                # logger.warning(e)  # Could result in lots of output with larger tag files
                pass

    logger.success('Script finished creating tags!')


if __name__ == '__main__':
    main()
