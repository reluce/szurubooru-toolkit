from pathlib import Path
from typing import Literal  # noqa TYP001

from loguru import logger
from pybooru.danbooru import Danbooru
from pybooru.moebooru import Moebooru
from tqdm import tqdm

from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.szurubooru import Post
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import get_posts_from_booru


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
        logger.warning('\nCould not find file url for post. It got probably removed from the site.')
        return

    try:
        file = download_media(file_url, md5)
    except Exception as e:
        logger.warning(f'\nCould not download post from {file_url}: {e}')
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
def main(booru: str, query: str) -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.import_from_booru['hide_progress']

        limit = config.import_from_booru['limit']

        if config.import_from_booru['deepbooru']:
            config.upload_media['auto_tag'] = True
            config.auto_tagger['saucenao'] = False
            config.auto_tagger['deepbooru'] = True
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
                disable=hide_progress,
            ):
                # Check by md5 hash if file is already uploaded
                try:
                    if booru == 'gelbooru':
                        md5 = Path(post.filename).stem
                    else:
                        md5 = post['md5']
                except KeyError:
                    logger.warning('\nPost has no MD5 attribute, it probably got removed from the site.')
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
        logger.info('\nReceived keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
