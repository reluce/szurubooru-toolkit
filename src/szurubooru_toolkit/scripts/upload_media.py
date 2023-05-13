from __future__ import annotations

import json
import os
import shutil
from glob import glob
from pathlib import Path

import requests
from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import Post
from szurubooru_toolkit import Szurubooru
from szurubooru_toolkit import config
from szurubooru_toolkit import shrink_img
from szurubooru_toolkit.scripts.auto_tagger import main as auto_tagger


szuru = Szurubooru(config.szurubooru['url'], config.szurubooru['username'], config.szurubooru['api_token'])


def get_files(upload_dir):
    """
    Reads recursively images/videos from upload_dir.

    Args:
        upload_dir: The directory on the local system which contains the images/videos you want to upload

    Returns:
        files: A list which contains the full path of each found images/videos (includes subdirectories)
    """

    allowed_extensions = ['jpg', 'jpeg', 'png', 'mp4', 'webm', 'gif', 'swf', 'webp']
    files_raw = list(
        filter(None, [glob(upload_dir + '/**/*.' + extension, recursive=True) for extension in allowed_extensions]),
    )
    files = [y for x in files_raw for y in x]

    return files


def get_media_token(szuru: Szurubooru, media: bytes) -> str:
    """Upload the media file to the temporary upload endpoint.

    We can access our temporary file with the token which receive from the response.

    Args:
        szuru (Szurubooru): A szurubooru object.
        media (bytes): The media file to upload as bytes.

    Returns:
        str: A token from szurubooru.

    Raises:
        Exception
    """

    post_url = szuru.szuru_api_url + '/uploads'

    try:
        response = requests.post(post_url, files={'content': media}, headers=szuru.headers)

        if 'description' in response.json():
            raise Exception(response.json()['description'])
        else:
            token = response.json()['token']
            return token
    except Exception as e:
        logger.critical(f'An error occured while getting the image token: {e}')


def check_similarity(szuru: Szurubooru, image_token: str) -> tuple | None:
    """Do a reverse image search with the temporary uploaded image.

    Args:
        image_token: An image token from szurubooru

    Returns:
        exact_post: Includes meta data of the post if an exact match was found
        similar_posts: Includes a list with all similar posts

    Raises:
        Exception
    """

    post_url = szuru.szuru_api_url + '/posts/reverse-search'
    metadata = json.dumps({'contentToken': image_token})

    try:
        response = requests.post(post_url, headers=szuru.headers, data=metadata)

        if 'description' in response.json():
            raise Exception(response.json()['description'])
        else:
            exact_post = response.json()['exactPost']
            similar_posts = response.json()['similarPosts']
            errors = False
            return exact_post, similar_posts, errors
    except Exception as e:
        print('')
        logger.warning(f'An error occured during the similarity check: {e}. Skipping post...')
        errors = True
        return False, [], errors


def upload_file(szuru: Szurubooru, post: Post) -> None:
    """Uploads/Moves our temporary image to 'production' with similar posts if any were found.

    Deletes file after upload has been completed.

    Args:
        szuru (Szurubooru): Szurubooru object to interact with the API.
        post (Post): Post object with attr `similar_posts` and `image_token`.

    Raises:
        Exception

    Returns:
        None
    """

    safety = post.safety if post.safety else config.upload_media['default_safety']
    source = post.source if post.source else ''

    post_url = szuru.szuru_api_url + '/posts'
    metadata = json.dumps(
        {
            'tags': post.tags,
            'safety': safety,
            'source': source,
            'relations': post.similar_posts,
            'contentToken': post.token,
        },
    )

    try:
        response = requests.post(post_url, headers=szuru.headers, data=metadata)

        if 'description' in response.json():
            raise Exception(response.json()['description'])
        else:
            return response.json()['id']
    except Exception as e:
        print('')
        logger.warning(f'An error occured during the upload for file "{post.file_path}": {e}')
        return None


def cleanup_dirs(dir: str) -> None:
    """Remove empty directories recursively from bottom to top.

    Args:
        dir (str): The directory under which to cleanup - dir is the root level and won't get deleted.

    Raises:
        OSError

    Returns:
        None
    """

    for root, dirs, files in os.walk(dir, topdown=False):
        for name in files:
            # Remove Thumbs.db file created by Windows
            if name == 'Thumbs.db':
                os.remove(os.path.join(root, name))
        for name in dirs:
            # Remove @eaDir directory created on Synology systems
            if name == '@eaDir':
                shutil.rmtree(os.path.join(root, name))
            try:
                os.rmdir(os.path.join(root, name))
            except OSError:
                pass


def eval_convert_image(file: bytes, file_ext: str, file_to_upload: str = None) -> bytes:
    """Evaluate if the image should be converted or shrunk and if so, do so.

    Args:
        file (bytes): The file as a byte string.
        file_ext (str): The file extension without a dot.
        file_to_upload (str): The file path of the file to upload (only for logging).

    Returns:
        bytes: The (converted) file as a byte string.
    """

    file_size = len(file)
    image = file

    try:
        if (
            config.upload_media['convert_to_jpg']
            and file_ext == 'png'
            and file_size > config.upload_media['convert_threshold']
            and config.upload_media['shrink']
        ):
            logger.debug(
                f'Converting and shrinking file, size {file_size} > {config.upload_media["convert_threshold"]}',
            )
            image = shrink_img(
                file,
                shrink_threshold=config.upload_media['shrink_threshold'],
                shrink_dimensions=config.upload_media['shrink_dimensions'],
                convert=True,
                convert_quality=config.upload_media['convert_quality'],
            )
        elif (
            config.upload_media['convert_to_jpg']
            and file_ext == 'png'
            and file_size > config.upload_media['convert_threshold']
        ):
            logger.debug(
                f'Converting file, size {file_size} > {config.upload_media["convert_threshold"]}',
            )
            image = shrink_img(
                file,
                convert=True,
                convert_quality=config.upload_media['convert_quality'],
            )
        elif config.upload_media['shrink']:
            logger.debug('Shrinking file...')
            image = shrink_img(
                file,
                shrink_threshold=config.upload_media['shrink_threshold'],
                shrink_dimensions=config.upload_media['shrink_dimensions'],
            )
    except OSError:
        print('')
        logger.warning(f'Could not shrink image {file_to_upload}. Keeping dimensions...')

    return image


def upload_post(file: bytes, file_ext: str, metadata: dict = None, file_path: str = None) -> bool:
    """Uploads given file to temporary file space in szurubooru.

    Args:
        file (bytes): The file as bytes
        file_ext (str): The file extension
        metadata (dict, optional): Attach metadata to the post. Defaults to None.
        file_path (str, optional): The path to the file (used for debugging). Defaults to None.

    Returns:
        bool: If the upload was successful or not
    """

    post = Post()

    if file_ext not in ['mp4', 'webm', 'gif']:
        post.media = eval_convert_image(file, file_ext, file_path)
    else:
        post.media = file

    post.token = get_media_token(szuru, post.media)
    post.exact_post, similar_posts, errors = check_similarity(szuru, post.token)

    if errors:
        return False

    threshold = 1 - float(config.upload_media['max_similarity'])

    for entry in similar_posts:
        if entry['distance'] < threshold and not post.exact_post:
            print()
            logger.debug(
                f'File "{file_path} is too similar to post {entry["post"]["id"]} ({100 - entry["distance"]}%)',
            )
            post.exact_post = True
            break

    if not post.exact_post:
        if not metadata:
            post.tags = config.upload_media['tags']
            post.safety = None
            post.source = None
        else:
            post.tags = metadata['tags']
            post.safety = metadata['safety']
            post.source = metadata['source']

        post.file_path = file_path

        post.similar_posts = []
        for entry in similar_posts:
            post.similar_posts.append(entry['post']['id'])

        post_id = upload_file(szuru, post)

        if not post_id:
            return

        # Tag post if enabled
        if config.upload_media['auto_tag']:
            auto_tagger(str(post_id), post.media)

    return True


def main(file_to_upload: bytes = None, file_ext: str = None, metadata: dict = None) -> int:
    """Main logic of the script."""

    try:
        if not file_to_upload:
            files_to_upload = get_files(config.upload_media['src_path'])
            from_import_from = False
        else:
            files_to_upload = file_to_upload
            from_import_from = True
            config.upload_media['hide_progress'] = True

        if files_to_upload:
            if not from_import_from:
                logger.info('Found ' + str(len(files_to_upload)) + ' file(s). Starting upload...')

                for file_path in tqdm(
                    files_to_upload,
                    ncols=80,
                    position=0,
                    leave=False,
                    disable=config.upload_media['hide_progress'],
                ):
                    with open(file_path, 'rb') as f:
                        file = f.read()
                    success = upload_post(file, file_ext=Path(file_path).suffix[1:], file_path=file_path)

                    if config.upload_media['cleanup'] and success:
                        if os.path.exists(file_path):
                            os.remove(file_path)

                if config.upload_media['cleanup']:
                    cleanup_dirs(config.upload_media['src_path'])  # Remove dirs after files have been deleted

                if not from_import_from:
                    logger.success('Script has finished uploading!')
            else:
                upload_post(file_to_upload, file_ext, metadata)
        else:
            logger.info('No files found to upload.')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
