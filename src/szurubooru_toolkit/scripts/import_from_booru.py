import argparse
from pathlib import Path
from typing import Literal  # noqa TYP001

from loguru import logger
from pybooru.danbooru import Danbooru
from pybooru.moebooru import Moebooru
from tqdm import tqdm

from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit import Post
from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import get_posts_from_booru


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
        print('')
        logger.warning(
            'Your query contains single quotes (\'). '
            'Consider using double quotes (") if the script doesn\'t behave as intended.',
        )

    return booru, query, limit


def import_post(
    booru: Literal['gelbooru', 'danbooru', 'konachan', 'yandere'],
    post: Post,
    file_ext: str,
    md5: str,
) -> None:
    """Download the post, extract its metadata upload it with the `upload-media` script.

    Args:
        booru (str): The Booru from which the post originated.
        post (Post): The szurubooru Post object.
        file_ext (str): The file extension of the media file.
        md5 (str): The md5 hash of the media file of the post.
    """

    try:
        file_url = post.file_url if booru == 'gelbooru' else post['file_url']
    except KeyError:
        print('')
        logger.warning('Could not find file url for post. It got probably removed from the site.')
        return

    try:
        file = download_media(file_url, md5)
    except Exception as e:
        print('')
        logger.warning(f'Could not download post from {file_url}: {e}')
        return

    match booru:
        case 'gelbooru':
            tags = post.tags
            safety = convert_rating(post.rating)
            source = 'https://gelbooru.com/index.php?page=post&s=view&id=' + str(post.id)
        case 'danbooru':
            tags = post['tag_string'].split()
            source = 'https://danbooru.donmai.us/posts/' + str(post['id'])
        case 'yandere':
            tags = post['tags'].split()
            source = 'https://yande.re/post/show/' + str(post['id'])
        case 'konachan':
            tags = post['tags'].split()
            source = 'https://konachan.com/post/show/' + str(post['id'])

    if not booru == 'gelbooru':
        safety = convert_rating(post['rating'])

    metadata = {'tags': tags, 'safety': safety, 'source': source}

    upload_media.main(file, file_ext, metadata)


@logger.catch
def main() -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    try:
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

            match booru:
                case 'danbooru':
                    booru_client = Danbooru('danbooru', config.danbooru['user'], config.danbooru['api_key'])
                case 'gelbooru':
                    booru_client = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
                case 'konachan':
                    booru_client = Moebooru('konachan', config.konachan['user'], config.konachan['password'])
                case 'yandere':
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
                try:
                    if booru == 'gelbooru':
                        md5 = Path(post.filename).stem
                    else:
                        md5 = post['md5']
                except KeyError:
                    print('')
                    logger.warning('Post has no MD5 attribute, it probably got removed from the site.')
                    continue

                try:
                    file_ext = Path(post.filename).suffix[1:]  # Gelbooru, remove dot at the end
                except AttributeError:
                    file_ext = post['file_url'].split('.')[-1]  # Other Boorus

                result = szuru.get_posts(f'md5:{md5}')

                try:
                    next(result)
                    logger.debug(f'Skipping post, already exists: {post}')
                except StopIteration:
                    import_post(booru, post, file_ext, md5)
                    logger.debug(f'Importing post: {post}')

        logger.success('Script finished importing!')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
