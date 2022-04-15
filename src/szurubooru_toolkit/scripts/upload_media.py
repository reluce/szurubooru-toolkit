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

    allowed_extensions = ['jpg', 'jpeg', 'png', 'mp4', 'webm', 'gif', 'swf']
    files_raw = list(
        filter(None, [glob(upload_dir + '/**/*.' + extension, recursive=True) for extension in allowed_extensions]),
    )
    files = [y for x in files_raw for y in x]

    return files


def get_image_token(szuru: Szurubooru, image: bytes) -> str:
    """Upload the image to the temporary uploads endpoint.

    We can access our temporary image with the image token.

    Args:
        szuru (Szurubooru):
        image (bytes): The image file to upload as bytes.

    Returns:
        str: An image token from szurubooru.

    Raises:
        Exception
    """

    post_url = szuru.szuru_api_url + '/uploads'

    try:
        response = requests.post(post_url, files={'content': image}, headers=szuru.headers)

        if 'description' in response.json():
            raise Exception(response.json()['description'])
        else:
            image_token = response.json()['token']
            return image_token
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
            return exact_post, similar_posts
    except Exception as e:
        logger.critical(f'An error occured during the similarity check: {e}')


def upload_file(szuru: Szurubooru, post: Post) -> None:
    """Uploads/Moves our temporary image to 'production' with similar posts if any were found.

    Deletes file after upload has been completed.

    Args:
        szuru (Szurubooru): Szurubooru object to interact with the API.
        post (Post): Post object with attr `similar_posts` and `image_token`.
        file_to_upload (str): Local file path of the file to upload.

    Raises:
        Exception
    """

    safety = post.safety if post.safety else 'unsafe'
    source = post.source if post.source else ''

    post_url = szuru.szuru_api_url + '/posts'
    metadata = json.dumps(
        {
            'tags': post.tags,
            'safety': safety,
            'source': source,
            'relations': post.similar_posts,
            'contentToken': post.image_token,
        },
    )

    try:
        response = requests.post(post_url, headers=szuru.headers, data=metadata)

        if 'description' in response.json():
            raise Exception(response.json()['description'])
        else:
            return response.json()['id']
    except Exception as e:
        logger.critical(f'An error occured during the upload: {e}')


def cleanup_dirs(dir: str) -> None:
    """Remove empty directories recursively from bottom to top.

    Args:
        dir (str): The directory under which to cleanup - dir is the root level and won't get deleted.

    Raises:
        OSError
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


def delete_posts(szuru: Szurubooru, start_id: int, finish_id: int):
    """If some posts unwanted posts were uploaded, you can delete those within the range of start_id to finish_id.

    Args:
        start_id: Start deleting from this post id
        finish_id: Stop deleting until this post id

    Raises:
        Exception
    """

    for id in range(start_id, finish_id + 1):
        post_url = szuru.szuru_api_url + '/post/' + str(id)
        try:
            response = requests.delete(post_url, headers=szuru.headers, data=json.dumps({'version': '1'}))
            if 'description' in response.json():
                raise Exception(response.json()['description'])
        except Exception as e:
            logger.critical(f'An error occured while deleting posts: {e}')


def upload_post(file_to_upload: Path, metadata: dict = None):
    post = Post()
    tmp_path = Path(config.auto_tagger['tmp_path'])

    # Save JPEG version of the file in the temp path
    file_size = os.path.getsize(str(file_to_upload))
    if (
        config.upload_media['convert_to_jpg']
        and file_to_upload.suffix == '.png'
        and file_size > config.upload_media['convert_threshold']
    ):
        logger.debug(
            f'Converting file, size {file_size} > {config.upload_media["convert_threshold"]}: {file_to_upload}',
        )
        shrink_img(tmp_path, file_to_upload, convert=True)

        with open(str(tmp_path / file_to_upload.stem) + '.jpg', 'rb') as f:
            post.image = f.read()

        converted = True
    else:
        with open(str(file_to_upload), 'rb') as f:
            post.image = f.read()
        converted = False

    post.image_token = get_image_token(szuru, post.image)
    post.exact_post, similar_posts = check_similarity(szuru, post.image_token)
    threshold = 1 - float(config.upload_media['max_similarity'])

    for entry in similar_posts:
        if entry['distance'] < threshold and not post.exact_post:
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

        post.similar_posts = []
        for entry in similar_posts:
            post.similar_posts.append(entry['post']['id'])

        post_id = upload_file(szuru, post)

        # Tag post if enabled
        if config.upload_media['auto_tag']:
            if file_to_upload.suffix not in ['.mp4', '.webm']:
                auto_tagger(str(post_id), file_to_upload)

    # Always clean up converted jpg files if present
    if converted:
        if os.path.exists(str(tmp_path / file_to_upload.stem) + '.jpg'):
            os.remove(str(tmp_path / file_to_upload.stem) + '.jpg')

    if config.upload_media['cleanup']:
        if os.path.exists(file_to_upload):
            os.remove(file_to_upload)


def main(file_to_upload: Path = None, metadata: dict = None) -> int:
    """Main logic of the script."""

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

            for file_to_upload in tqdm(
                files_to_upload,
                ncols=80,
                position=0,
                leave=False,
                disable=config.upload_media['hide_progress'],
            ):
                upload_post(Path(file_to_upload))

            if config.upload_media['cleanup']:
                cleanup_dirs(config.upload_media['src_path'])  # Remove dirs after files have been deleted

            if not from_import_from:
                logger.success('Script has finished uploading.')
        else:
            upload_post(file_to_upload, metadata)

    else:
        logger.info('No files found to upload.')


if __name__ == '__main__':
    main()
