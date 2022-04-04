import argparse
import sys
import urllib
from pathlib import Path

from loguru import logger
from pybooru.moebooru import Moebooru
from tqdm import tqdm

from szurubooru_toolkit import Danbooru
from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import upload_media


sys.tracebacklimit = 0


def parse_args() -> tuple:
    """
    Parse the input args to the script auto_tagger.py and set the object attributes accordingly.
    """

    parser = argparse.ArgumentParser(
        description='This script downloads and tags posts from various Boorus based on your input query.',
    )

    parser.add_argument(
        '--booru',
        default=None,
        help='Specify the Booru which you want to query',
    )
    parser.add_argument(
        'query',
        help='Specify the query for the posts you want to download and tag',
    )

    args = parser.parse_args()

    booru = args.booru
    logger.debug(f'booru = {booru}')

    query = args.query
    logger.debug(f'query = {query}')
    if '\'' in query:
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return booru, query


def get_posts_from_danbooru(danbooru: Danbooru, query: str) -> list:
    results = danbooru.client.post_list(limit=100, tags=query)

    yield len(results)

    yield from results


def upload_post_from_danbooru(post):
    try:
        file_url = post['file_url']
    except IndexError:
        file_url = 'https://danbooru.donmai.us' + post['source']

    filename = file_url.split('/')[-1]
    dest_path = Path(config.auto_tagger['tmp_path']) / filename

    try:
        urllib.request.urlretrieve(file_url, dest_path)
    except Exception as e:
        logger.warning(e)
        return

    tags = post['tag_string_general'].split()
    tags.extend(post['tag_string_character'].split())
    tags.extend(post['tag_string_copyright'].split())
    tags.extend(post['tag_string_artist'].split())
    tags.extend(post['tag_string_meta'].split())

    upload_media.main(tags, str(dest_path))


async def get_posts_from_gelbooru(gelbooru: Gelbooru, query: str) -> list:
    results = await gelbooru.client.search_posts(tags=query)

    for post in results:
        yield post


def upload_post_from_gelbooru(post):
    pass


def get_posts_from_konachan(konachan: Moebooru, query: str) -> list:
    pass


def upload_post_from_konachan(post):
    pass


def get_posts_from_yandere(yandere: Moebooru, query: str) -> list:
    pass


def upload_post_from_yandere(post):
    pass


@logger.catch
def main() -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    logger.info('Initializing script...')

    booru, query = parse_args()

    logger.info(f'Retrieving posts from {booru} with query "{query}"...')

    if booru == 'danbooru':
        danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
        posts = get_posts_from_danbooru(danbooru, query)
    elif booru == 'gelbooru':
        gelbooru = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
        posts = get_posts_from_danbooru(gelbooru, query)
    elif booru == 'konachan':
        konachan = Moebooru('konachan', config.konachan['user'], config.konachan['password'])
        posts = get_posts_from_konachan(konachan, query)
    elif booru == 'yandere':
        yandere = Moebooru('yandere', config.yandere['user'], config.yandere['password'])
        posts = get_posts_from_yandere(yandere, query)

    total_posts = next(posts)
    logger.info(f'Found {total_posts} posts. Start importing...')

    for post in tqdm(
        posts,
        ncols=80,
        position=0,
        leave=False,
        total=int(total_posts),
        disable=config.auto_tagger['hide_progress'],
    ):
        if booru == 'danbooru':
            upload_post_from_danbooru(post)
        elif booru == 'gelbooru':
            upload_post_from_gelbooru(post)
        elif booru == 'konachan':
            upload_post_from_konachan(post)
        elif booru == 'yandere':
            upload_post_from_yandere(post)

    logger.success('Script finished importing!')


if __name__ == '__main__':
    main()
