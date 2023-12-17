import argparse
import glob
import json
import os
import shutil
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import Pixiv
from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import convert_tags
from szurubooru_toolkit.utils import extract_twitter_artist
from szurubooru_toolkit.utils import generate_src
from szurubooru_toolkit.utils import invoke_gallery_dl


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
        '-v',
        '--verbose',
        action='store_true',
        help='Show download progress of gallery-dl script.',
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

    return args.range, args.urls, args.input_file, args.cookies, args.verbose


def set_tags(metadata) -> list:
    artist = ''
    allow_tags_for_sites = ['sankaku', 'danbooru', 'gelbooru', 'konachan', 'yandere', 'fanbox', 'pixiv', 'twitter']

    if metadata['site'] in allow_tags_for_sites:
        try:
            if metadata['site'] in ['fanbox', 'pixiv']:
                metadata['tags'] = convert_tags(metadata['tags'])
            elif metadata['site'] == 'twitter':
                metadata['tags'] = convert_tags(metadata['hashtags'])
            else:
                if isinstance(metadata['tags'], str):
                    metadata['tags'] = metadata['tags'].split()
        except KeyError:
            if isinstance(metadata['tag_string'], str):
                metadata['tags'] = metadata['tag_string'].split()
            else:
                metadata['tags'] = []
    else:
        metadata['tags'] = []

    if metadata['site'] in ['fanbox', 'pixiv', 'e-hentai']:
        if metadata['site'] == 'e-hentai':
            for tag in metadata['tags']:
                if tag.startswith('artist'):
                    index = tag.find(':')
                    if index != -1:
                        artist = tag[index + 1 :]  # noqa E203
                        artist = artist.replace(' ', '_')
        elif metadata['site'] in ['fanbox', 'pixiv']:
            try:
                artist = metadata['user']['name']
            except KeyError:
                pass

        if artist:
            canon_artist = Pixiv.extract_pixiv_artist(artist)
            if canon_artist:
                metadata['tags'].append(canon_artist)

    return metadata['tags']


@logger.catch
def main(urls: list = [], cookies: str = '', limit_range: str = ':100') -> None:
    if not urls:
        limit_range, urls, input_file, cookies, verbose = parse_args()
    else:
        if not limit_range:
            limit_range = ':100'
        input_file = ''
        verbose = False

    if config.import_from_url['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['md5_search_enabled'] = False
        config.auto_tagger['saucenao_enabled'] = False
        config.auto_tagger['deepbooru_enabled'] = True
    else:
        config.upload_media['auto_tag'] = False

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
        'fanbox': {'url_keyword': 'fanbox', 'user_key': None, 'password_key': None},
        'pixiv': {'url_keyword': 'pixiv', 'user_key': None, 'password_key': None},
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

    params = [f'--range={limit_range}', '--write-metadata']

    if user and password and user != 'none' and password != 'none':
        params += [f'--username={user}', f'--password={password}']

    if cookies:
        params += [f'--cookies={cookies}']

    if input_file:
        params += [f'--input-file={input_file}']

    if not verbose:
        params.append('-q')

    download_dir = invoke_gallery_dl(urls, config.import_from_url['tmp_path'], params)

    files = [file for file in glob.glob(f'{download_dir}/*') if Path(file).suffix not in ['.psd', '.json']]

    logger.info(f'Downloaded {len(files)} post(s). Start importing...')

    saucenao_limit_reached = False

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

            if 'tags' in metadata or 'tag_string' in metadata or 'hashtags' in metadata:
                metadata['tags'] = set_tags(metadata)
            else:
                metadata['tags'] = []

            # As Twitter doesn't provide any tags compared to other sources, we try to auto tag it.
            if site == 'twitter':
                metadata['tags'] += extract_twitter_artist(metadata)
                config.auto_tagger['md5_search_enabled'] = True
                config.auto_tagger['saucenao_enabled'] = True
            else:
                config.auto_tagger['md5_search_enabled'] = False
                config.auto_tagger['saucenao_enabled'] = False

            with open(file, 'rb') as file_b:
                saucenao_limit_reached = upload_media.main(file_b.read(), Path(file).suffix[1:], metadata, saucenao_limit_reached)

    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
