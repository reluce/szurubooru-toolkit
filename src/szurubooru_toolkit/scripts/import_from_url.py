import argparse
import glob
import json
import os
import subprocess
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import Danbooru
from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import generate_src


def parse_args() -> tuple:
    """Parse the input args to the script import_from_url.py and set the object attributes accordingly."""

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
        'urls',
        nargs='*',
        help='One or multiple URLs to the posts you want to download and tag',
    )

    args = parser.parse_args()

    if not args.urls and not args.input_file:
        parser.print_help()
        exit(1)

    return args.range, args.urls, args.input_file


def set_tags(metadata) -> list:
    artist = ''

    if metadata['site'] == 'e-hentai':
        for tag in metadata['tags']:
            if tag.startswith('artist'):
                index = tag.find(':')
                if index != -1:
                    artist = tag[index + 1 :]  # noqa E203

                    danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
                    canon_artist = danbooru.search_artist(artist)
                    if canon_artist:
                        metadata['tags'] = [canon_artist]
                    else:
                        metadata['tags'] = []

        if not artist:
            metadata['tags'] = []
    else:
        try:
            if isinstance(metadata['tags'], str):
                metadata['tags'] = metadata['tags'].split()
        except KeyError:
            if isinstance(metadata['tag_string'], str):
                metadata['tags'] = metadata['tag_string'].split()

    return metadata['tags']


@logger.catch
def main() -> None:
    """Calls gallery-dl and parse output.

    Currently supports only Danbooru, Gelbooru, Konachan, Yandere and Sankaku.
    """

    limit_range, urls, input_file = parse_args()

    if config.import_from_url['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['saucenao_enabled'] = False
        config.auto_tagger['deepbooru_enabled'] = True
    else:
        config.upload_media['auto_tag'] = False

    base_command = [
        'gallery-dl',
        '-q',
        '--write-metadata',
        f'-D={config.import_from_url["tmp_path"]}',
    ]

    if input_file and not urls:
        logger.info(f'Downloading posts from input file "{input_file}"...')
    elif input_file and urls:
        logger.info(f'Downloading posts from input file "{input_file}" and URLs {urls}...')
    else:
        logger.info(f'Downloading posts from URLs {urls}...')

    if any('sankaku' in url for url in urls):
        site = 'sankaku'
        user = config.sankaku['user']
        password = config.sankaku['password']
    elif any('danbooru' in url for url in urls):
        site = 'danbooru'
        user = config.danbooru['user']
        password = config.danbooru['api_key']
    elif any('gelbooru' in url for url in urls):
        site = 'gelbooru'
        user = config.gelbooru['user']
        password = config.gelbooru['api_key']
    elif any('konachan' in url for url in urls):
        site = 'konachan'
        user = config.konachan['user']
        password = config.konachan['password']
    elif any('yande.re' in url for url in urls):
        site = 'yandere'
        user = config.yandere['user']
        password = config.yandere['password']
    elif any('e-hentai' in url for url in urls):
        site = 'e-hentai'
        user = None
        password = None
    else:
        site = None
        user = None
        password = None

    if user and password and (user != 'None' and password != 'None'):
        if input_file:
            command = (
                base_command
                + [
                    f'--username={user}',
                    f'--password={password}',
                    f'--range={limit_range}',
                    f'--input-file={input_file}',
                ]
                + urls
            )
        else:
            command = base_command + [f'--username={user}', f'--password={password}', f'--range={limit_range}'] + urls

        subprocess.run(command)
    else:
        if input_file:
            command = base_command + [f'--range={limit_range}', f'--input-file={input_file}'] + urls
        else:
            command = base_command + [f'--range={limit_range}'] + urls
        subprocess.run(command)

    files = [file for file in glob.glob(config.import_from_url['tmp_path'] + '/*') if not Path(file).suffix == '.json']

    logger.info(f'Downloaded {len(files)} post(s). Start importing...')

    for file in tqdm(
        files,
        ncols=80,
        position=0,
        leave=False,
        disable=config.import_from_url['hide_progress'],
    ):
        with open(file + '.json') as f:
            metadata = json.load(f)
            metadata['site'] = site
            metadata['source'] = generate_src(metadata)
            metadata['safety'] = convert_rating(metadata['rating'])
            metadata['tags'] = set_tags(metadata)

            with open(file, 'rb') as file_b:
                upload_media.main(file_b.read(), Path(file).suffix[1:], metadata)

            if os.path.exists(file):
                os.remove(file)
            if os.path.exists(file + '.json'):
                os.remove(file + '.json')

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
