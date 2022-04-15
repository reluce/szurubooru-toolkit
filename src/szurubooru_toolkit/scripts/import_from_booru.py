import argparse
import os
import urllib
from math import ceil
from pathlib import Path

import requests
from loguru import logger
from lxml import etree
from pybooru.danbooru import Danbooru
from pybooru.exceptions import PybooruHTTPError
from pybooru.moebooru import Moebooru
from syncer import sync
from tqdm import tqdm

from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import get_md5sum


def parse_args() -> tuple:
    """Parse the input args to the script auto_tagger.py and set the object attributes accordingly."""

    parser = argparse.ArgumentParser(
        description='This script downloads and tags posts from various Boorus based on your input query.',
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Limit the search results to be returned (default: 100)',
    )

    parser.add_argument(
        'booru',
        choices=['danbooru', 'gelbooru', 'konachan', 'yandere', 'all'],
        help='Specify the Booru which you want to query. Use all to query all Boorus.',
    )

    parser.add_argument(
        'query',
        help='The search query for the posts you want to download and tag',
    )

    args = parser.parse_args()

    limit = args.limit

    booru = args.booru
    logger.debug(f'booru = {booru}')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return booru, query, limit


def get_posts_from_booru(booru, query: str, limit: int):
    """Retrieve posts from Boorus based on search query and yields them."""

    if not limit:
        # Get the total count of posts for the query first
        if isinstance(booru, Gelbooru):
            api_url = 'https://gelbooru.com/index.php?page=dapi&s=post&q=index'
            xml_result = requests.get(f'{api_url}&tags={query}')
            root = etree.fromstring(xml_result.content)
            total = root.attrib['count']
        elif isinstance(booru, Danbooru):
            if not limit:
                try:
                    total = booru.count_posts(tags=query)['counts']['posts']
                except PybooruHTTPError:
                    logger.critical('Importing from Danbooru accepts only a maximum of two tags for you search query!')
                    exit()
        else:  # Moebooru (Yandere + Konachan)
            xml_result = requests.get(f'{booru.site_url}/post.xml?tags={query}')
            root = etree.fromstring(xml_result.content)
            total = root.attrib['count']

        pages = ceil(int(total) / 100)  # Max results per page are 100 for every Booru
        results = []

        if pages > 1:
            for page in range(1, pages + 1):
                if isinstance(booru, Gelbooru):
                    results.append(sync(booru.client.search_posts(page=page, tags=query.split())))
                else:
                    try:
                        results.append(booru.post_list(page=page, tags=query))
                    except PybooruHTTPError:
                        logger.critical(
                            'Importing from Danbooru accepts only a maximum of two tags for you search query!',
                        )
                        exit()

            results = [result for result in results for result in result]
        else:
            if isinstance(booru, Gelbooru):
                results = sync(booru.client.search_posts(tags=query.split()))
            else:
                results = booru.post_list(tags=query)
    else:
        if isinstance(booru, Gelbooru):
            results = sync(booru.client.search_posts(limit=limit, tags=query.split()))
        else:
            try:
                results = booru.post_list(limit=limit, tags=query)
            except PybooruHTTPError:
                logger.critical('Importing from Danbooru accepts only a maximum of two tags for you search query!')
                exit()

    yield len(results)
    yield from results


def download_post(file_url: str, booru, post) -> None:
    """Downloads the post from `file_url`."""

    filename = file_url.split('/')[-1]
    file_path = Path(config.auto_tagger['tmp_path']) / filename  # Where the file gets temporarily saved to

    for _ in range(1, 3):
        try:
            urllib.request.urlretrieve(file_url, file_path)
        except Exception as e:
            logger.warning(f'Could not download post from {file_url}: {e}')

        md5sum = get_md5sum(file_path)

        if booru == 'gelbooru':
            if Path(post.filename).stem == md5sum:
                return file_path
        else:
            if post['md5'] == md5sum:
                return file_path


def import_post(booru, post) -> None:
    """Download the post, extract its metadata upload it with the `upload-media` script."""

    try:
        file_url = post.file_url if booru == 'gelbooru' else post['file_url']
    except KeyError:
        logger.warning('Could not find file url for post. It got probably removed from the site.')
        return

    try:
        file_path = download_post(file_url, booru, post)
    except Exception as e:
        logger.warning(f'Could not download post from {file_url}: {e}')
        return

    if booru == 'gelbooru':
        tags = post.tags
        safety = convert_rating(post.rating)
        source = 'https://gelbooru.com/index.php?page=post&s=view&id=' + str(post.id)
    elif booru == 'danbooru':
        tags = post['tag_string'].split()
        source = 'https://danbooru.donmai.us/posts/' + str(post['id'])
    elif booru == 'yandere':
        tags = post['tags'].split()
        source = 'https://yande.re/post/show/' + str(post['id'])
    elif booru == 'konachan':
        tags = post['tags'].split()
        source = 'https://konachan.com/post/show/' + str(post['id'])

    if not booru == 'gelbooru':
        safety = convert_rating(post['rating'])

    metadata = {'tags': tags, 'safety': safety, 'source': source}

    upload_media.main(file_path, metadata)

    if os.path.exists(str(file_path)):
        os.remove(str(file_path))


@logger.catch
def main() -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    logger.info('Initializing script...')

    booru, query, limit = parse_args()

    if config.import_from_booru['deepbooru_enabled']:
        config.upload_media['auto_tag'] = True
        config.auto_tagger['saucenao_enabled'] = False
        config.auto_tagger['deepbooru_enabled'] = True
    else:
        config.upload_media['auto_tag'] = False

    if booru == 'all':
        boorus = ['danbooru', 'gelbooru', 'yandere', 'konachan']
    else:
        boorus = [booru]

    for booru in boorus:
        logger.info(f'Retrieving posts from {booru} with query "{query}"...')

        if booru == 'danbooru':
            booru_client = Danbooru('danbooru', config.danbooru['user'], config.danbooru['api_key'])
        elif booru == 'gelbooru':
            booru_client = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
        elif booru == 'konachan':
            booru_client = Moebooru('konachan', config.konachan['user'], config.konachan['password'])
        elif booru == 'yandere':
            booru_client = Moebooru('yandere', config.yandere['user'], config.yandere['password'])

        posts = get_posts_from_booru(booru_client, query, limit)

        total_posts = next(posts)
        logger.info(f'Found {total_posts} posts. Start importing...')

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=config.import_from_booru['hide_progress'],
        ):
            # Check by md5 hash if file is already uploaded
            if booru == 'gelbooru':
                result = szuru.get_posts(f'md5:{Path(post.filename).stem}')
            else:
                try:
                    result = szuru.api.search_post(f'md5:{post["md5"]}')
                except KeyError:
                    logger.warning('Post has no MD5 attribute, it probably got removed from the site.')

            try:
                next(result)
                logger.debug(f'Skipping post, already exists: {post}')
            except StopIteration:
                import_post(booru, post)
                logger.debug(f'Importing post: {post}')

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
