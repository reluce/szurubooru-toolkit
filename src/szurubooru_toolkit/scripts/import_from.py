import argparse
import glob
import json
import os
import subprocess
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating


def parse_args() -> tuple:
    """Parse the input args to the script import_from.py and set the object attributes accordingly."""

    parser = argparse.ArgumentParser(
        description='This script downloads and tags posts from various Boorus based on your input query.',
    )

    parser.add_argument(
        '--range',
        default='1-100',
        help=(
            'Index range(s) specifying which files to download. '
            'These can be either a constant value, range, or slice '
            "(e.g. '5', '8-20', or '1:24:3')"
        ),
    )

    parser.add_argument(
        '--input-file',
        help='Download URLs found in FILE.',
    )

    parser.add_argument(
        'url',
        nargs='*',
        help='The URL for the posts you want to download and tag',
    )

    args = parser.parse_args()

    if not args.url and not args.input_file:
        parser.print_help()
        exit(1)

    return args.range, args.url[0], args.input_file


def extract_metadata(file_path) -> tuple:
    file_name = Path(file_path).name
    index = file_name.index('_')
    second_index = file_name.find('_', index + 1)

    site = file_name[:index]
    id = file_name[index + 1 : second_index]  # noqa

    return site, id


def generate_src(file_path: str) -> str:
    """Generate and return post source URL.

    Args:
        file_path (str): The path to the generated metadata file from gallery-dl.

    Returns:
        str: The source URL of the post.
    """

    site, id = extract_metadata(file_path)

    if site == 'danbooru':
        src = 'https://danbooru.donmai.us/posts/' + id
    elif site == 'gelbooru':
        src = 'https://gelbooru.com/index.php?page=post&s=view&id=' + id
    elif site == 'konachan':
        src = 'https://konachan.com/post/show/' + id
    elif site == 'sankaku':
        src = 'https://chan.sankakucomplex.com/post/show/' + id
    elif site == 'yandere':
        src = 'https://yande.re/post/show/' + id
    else:
        src = None

    return src


@logger.catch
def main() -> None:
    """Calls gallery-dl and parse output.

    Currently supports only Danbooru, Gelbooru, Konachan, Yandere and Sankaku.
    """

    limit_range, url, input_file = parse_args()

    if config.import_from_booru['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['saucenao_enabled'] = False
        config.auto_tagger['deepbooru_enabled'] = True
    else:
        config.upload_media['auto_tag'] = False

    if input_file:
        logger.info(f'Downloading posts from input file {input_file}...')
        subprocess.run(
            [
                'gallery-dl',
                '-q',
                '--write-metadata',
                f'-D={config.import_from["tmp_path"]}',
                f'--input-file={input_file}',
            ],
        )
    else:
        logger.info(f'Downloading posts from URL {url}...')

        if 'sankaku' in url:
            user = config.sankaku['user']
            password = config.sankaku['password']
        elif 'danbooru' in url:
            user = config.danbooru['user']
            password = config.danbooru['api_key']
        elif 'gelbooru' in url:
            user = config.gelbooru['user']
            password = config.gelbooru['api_key']
        elif 'konachan' in url:
            user = config.konachan['user']
            password = config.konachan['password']
        elif 'yandere' in url:
            user = config.yandere['user']
            password = config.yandere['password']
        else:
            user = None
            password = None

        if user and password and (user != 'None' and password != 'None'):
            subprocess.run(
                [
                    'gallery-dl',
                    '-q',
                    '--write-metadata',
                    f'--username={user}',
                    f'--password={password}',
                    f'--range={limit_range}',
                    f'-D={config.import_from["tmp_path"]}',
                    url,
                ],
            )
        else:
            subprocess.run(
                [
                    'gallery-dl',
                    '-q',
                    '--write-metadata',
                    f'--range={limit_range}',
                    f'-D={config.import_from["tmp_path"]}',
                    url,
                ],
            )

    files = [file for file in glob.glob(config.import_from['tmp_path'] + '/*') if not Path(file).suffix == '.json']

    logger.info(f'Downloaded {len(files)} post(s). Start importing...')

    for file in tqdm(
        files,
        ncols=80,
        position=0,
        leave=False,
        disable=config.import_from['hide_progress'],
    ):
        with open(file + '.json') as f:
            metadata = json.load(f)
            metadata['source'] = generate_src(file)
            metadata['safety'] = convert_rating(metadata['rating'])

            try:
                if isinstance(metadata['tags'], str):
                    metadata['tags'] = metadata['tags'].split()
            except KeyError:
                if isinstance(metadata['tag_string'], str):
                    metadata['tags'] = metadata['tag_string'].split()

            with open(file, 'rb') as file_b:
                upload_media.main(file_b.read(), Path(file).suffix[1:], metadata)

            if os.path.exists(file):
                os.remove(file)
            if os.path.exists(file + '.json'):
                os.remove(file + '.json')

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
