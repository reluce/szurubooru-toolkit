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
from szurubooru_toolkit.utils import extract_twitter_artist
from szurubooru_toolkit.utils import generate_src


def parse_args() -> tuple:
    """Parse the input args to the script import_from_url.py and set the object attributes accordingly."""

    parser = argparse.ArgumentParser(
        description='This script downloads and tags posts from various Boorus based on your input query.',
    )

    parser.add_argument(
        '--range',
        default=':100',
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
        '--cookies',
        help='Path to a cookies file for gallery-dl to consume. Used for authentication.',
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

    return args.range, args.urls, args.input_file, args.cookies


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

    limit_range, urls, input_file, cookies = parse_args()

    if config.import_from_url['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['md5_search_enabled'] = False
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

    url_mappings = {
        'sankaku': {'url_keyword': 'sankaku', 'user_key': 'user', 'password_key': 'password'},
        'danbooru': {'url_keyword': 'danbooru', 'user_key': 'user', 'password_key': 'api_key'},
        'gelbooru': {'url_keyword': 'gelbooru', 'user_key': 'user', 'password_key': 'api_key'},
        'konachan': {'url_keyword': 'konachan', 'user_key': 'user', 'password_key': 'password'},
        'yandere': {'url_keyword': 'yande.re', 'user_key': 'user', 'password_key': 'password'},
        'e-hentai': {'url_keyword': 'e-hentai', 'user_key': None, 'password_key': None},
        'twitter': {'url_keyword': 'twitter', 'user_key': None, 'password_key': None},
        'kemono': {'url_keyword': 'kemono', 'user_key': None, 'password_key': None},
    }

    site = None
    user = None
    password = None

    for url in urls:
        for site_key, site_data in url_mappings.items():
            if site_data['url_keyword'] in url:
                site = site_key
                try:
                    user = getattr(config, site_key)[site_data['user_key']]
                    password = getattr(config, site_key)[site_data['password_key']]
                except (KeyError, AttributeError):
                    user = None
                    password = None
                break

        if site is not None:
            break

    command = base_command + [f'--range={limit_range}']

    if user and password and user != 'none' and password != 'none':
        command += [f'--username={user}', f'--password={password}']

    if cookies:
        command += [f'--cookies={cookies}']

    if input_file:
        command += [f'--input-file={input_file}']

    command += urls

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

            if 'rating' in metadata:
                metadata['safety'] = convert_rating(metadata['rating'])
            else:
                metadata['safety'] = config.upload_media['default_safety']

            if 'tags' in metadata:
                metadata['tags'] = set_tags(metadata)
            elif site == 'twitter':
                metadata['tags'] = extract_twitter_artist(metadata)
            else:
                metadata['tags'] = []

            # As Twitter doesn't provide any tags compared to other sources, we try to auto tag it.
            if site == 'twitter':
                config.auto_tagger['md5_search_enabled'] = True
                config.auto_tagger['saucenao_enabled'] = True
            else:
                config.auto_tagger['md5_search_enabled'] = False
                config.auto_tagger['saucenao_enabled'] = False

            with open(file, 'rb') as file_b:
                upload_media.main(file_b.read(), Path(file).suffix[1:], metadata)

            if os.path.exists(file):
                os.remove(file)
            if os.path.exists(file + '.json'):
                os.remove(file + '.json')

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
