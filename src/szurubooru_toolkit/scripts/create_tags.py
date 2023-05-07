import argparse
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.danbooru import Danbooru
from szurubooru_toolkit.szurubooru import TagExistsError


def parse_args() -> tuple:
    """Parse the input args to the script create_tags.py and set the variables accordingly."""

    parser = argparse.ArgumentParser(
        description='This script will read the tags from specified file and creates them in your szurubooru.',
    )

    parser.add_argument(
        '--tag-file',
        default=None,
        help='Specify the local path to the file containing the tags and categories. \
            If specified, ignores other arguments (default: ./misc/tags/tags.txt).',
    )
    parser.add_argument(
        '--query',
        default='*',
        help='Search for specific tags (default: "*").',
    )
    parser.add_argument(
        '--min-post-count',
        default=10,
        help='The minimum amount of posts the tag should have been used in (default: 10).',
    )
    parser.add_argument(
        '--limit',
        default=100,
        help='The amount of tags that should be downloaded. Start from the most recent ones (default: 100).',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        default=False,
        help='Overwrite tag category if the tag already exists.',
    )

    args = parser.parse_args()

    if args.tag_file:
        args.tag_file = Path(args.tag_file)

    return args.tag_file, args.query, int(args.min_post_count), int(args.limit), args.overwrite


def convert_tag_category(category: int) -> str:
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
def main() -> None:
    """Read tags from file and create them in szurubooru."""

    try:
        tags_file, query, min_post_count, limit, overwrite = parse_args()

        if tags_file:
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
        else:
            danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
            results = danbooru.download_tags(query, min_post_count, limit)

            for result in results:
                for tag in result:
                    try:
                        szuru.create_tag(tag['name'], convert_tag_category(tag['category']), overwrite)
                    except TagExistsError as e:  # noqa F841
                        pass

        logger.success('Script finished creating tags!')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
