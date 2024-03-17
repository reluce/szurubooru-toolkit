from __future__ import annotations

import json
import os
import shutil
from glob import glob
from pathlib import Path

import requests
from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.scripts import auto_tagger
from szurubooru_toolkit.scripts import tag_posts
from szurubooru_toolkit.scripts.import_from_url import set_tags
from szurubooru_toolkit.szurubooru import Post
from szurubooru_toolkit.szurubooru import Szurubooru
from szurubooru_toolkit.utils import convert_rating, extract_twitter_artist, get_md5sum, get_site
from szurubooru_toolkit.utils import shrink_img


def get_files(upload_dir: str) -> list:
    """
    Reads recursively images/videos from upload_dir.

    This function searches for files with the extensions 'jpg', 'jpeg', 'png', 'mp4', 'webm', 'gif', 'swf', and 'webp'
    in the specified directory and its subdirectories.

    Args:
        upload_dir (str): The directory on the local system which contains the images/videos you want to upload.

    Returns:
        list: A list which contains the full path of each found images/videos (includes subdirectories).
    """

    allowed_extensions = ['jpg', 'jpeg', 'png', 'mp4', 'webm', 'gif', 'swf', 'webp']
    files_raw = list(
        filter(None, [glob(upload_dir + '/**/*.' + extension, recursive=True) for extension in allowed_extensions]),
    )
    files = [y for x in files_raw for y in x]

    return files


def get_media_token(szuru: Szurubooru, media: bytes) -> str:
    """
    Upload the media file to the temporary upload endpoint.

    This function uploads a media file to the temporary upload endpoint of szurubooru and returns the token received
    from the response. This token can be used to access the temporary file.

    Args:
        szuru (Szurubooru): A szurubooru object.
        media (bytes): The media file to upload as bytes.

    Returns:
        str: A token from szurubooru.

    Raises:
        Exception: If the response contains a 'description' field, an exception is raised with the description as the
                   error message.
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
    """
    Do a reverse image search with the temporary uploaded image.

    This function uses the temporary image token to perform a reverse image search on szurubooru. It returns a tuple
    containing the metadata of the exact match post and a list of similar posts, if any.

    Args:
        szuru (Szurubooru): A szurubooru object.
        image_token (str): An image token from szurubooru.

    Returns:
        tuple: A tuple containing the metadata of the exact match post and a list of similar posts, if any.
        None: If no exact match or similar posts are found.

    Raises:
        Exception: If the response contains a 'description' field, an exception is raised with the description as the
                   error message.
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
        logger.warning(f'An error occured during the similarity check: {e}. Skipping post...')
        errors = True
        return False, [], errors


def upload_file(szuru: Szurubooru, post: Post) -> None:
    """
    Uploads the temporary image to szurubooru, making it visible to all users.

    This function uploads a temporary image to szurubooru, making it accessible and visible to all users. It also sets
    the tags, safety, source, relations, and contentToken of the post. If similar posts were found during the similarity
    check, they are added as relations. The file is deleted after the upload has been completed.

    Args:
        szuru (Szurubooru): A szurubooru object.
        post (Post): Post object with attr `similar_posts` and `image_token`.

    Raises:
        Exception: If the response contains a 'description' field, an exception is raised with the description as the
                   error message.

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
        logger.warning(f'An error occured during the upload for file "{post.file_path}": {e}')
        return None


def cleanup_dirs(dir: str) -> None:
    """
    Remove empty directories recursively from bottom to top.

    This function removes empty directories under the specified directory, starting from the deepest level and working
    its way up. It also removes 'Thumbs.db' files created by Windows and '@eaDir' directories created on Synology systems.
    The root directory itself is not deleted.

    Args:
        dir (str): The directory under which to cleanup - dir is the root level and won't get deleted.

    Raises:
        OSError: If an error occurs while removing a directory.

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


def eval_convert_image(file: bytes, file_ext: str, file_to_upload: str = None) -> tuple[bytes | str]:
    """
    Evaluate if the image should be converted or shrunk and if so, do so.

    This function checks if the image file should be converted to a different format or shrunk based on the global
    configuration settings. If the image is a PNG and its size is greater than the conversion threshold, it will be
    converted to a JPG. If the 'shrink' setting is enabled, the image will also be shrunk.

    Args:
        file (bytes): The file as a byte string.
        file_ext (str): The file extension without a dot.
        file_to_upload (str, optional): The file path of the file to upload (only for logging). Defaults to None.

    Returns:
        Tuple[bytes, str]: The (possibly converted and/or shrunk) file as a byte string and the MD5 sum of the original
                           file.
    """

    file_size = len(file)
    original_md5 = get_md5sum(file)
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
        elif config.upload_media['convert_to_jpg'] and file_ext == 'png' and file_size > config.upload_media['convert_threshold']:
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
        logger.warning(f'Could not shrink image {file_to_upload}. Keeping dimensions...')

    return image, original_md5




def upload_post(
    file: bytes,
    file_ext: str,
    metadata: dict = None,
    file_path: str = None,
    saucenao_limit_reached: bool = False,
) -> tuple[bool, bool]:
    """
    Uploads given file to szurubooru and checks for similar posts.

    This function uploads a file to szurubooru and checks for similar posts. If the file is not a video or GIF, it is
    evaluated for conversion or shrinking. The file is then uploaded to szurubooru and a similarity check is performed.
    If any errors occur during the similarity check, the function returns False.

    Args:
        file (bytes): The file as bytes.
        file_ext (str): The file extension.
        metadata (dict, optional): Attach metadata to the post. Defaults to None.
        file_path (str, optional): The path to the file (used for debugging). Defaults to None.
        saucenao_limit_reached (bool, optional): If the SauceNAO limit has been reached. Defaults to False.

    Returns:
        Tuple[bool, bool]: A tuple where the first element indicates if the upload was successful or not, and the second
                           element indicates if the SauceNAO limit has been reached.
    """


    post = Post()
    post.source = None
    original_md5 = ''

    if file_ext not in ['mp4', 'webm', 'gif']:
        post.media, original_md5 = eval_convert_image(file, file_ext, file_path)
    else:
        post.media = file

    post.token = get_media_token(szuru, post.media)
    logger.debug(
        f'File post token: {post.token} ',
    )
    post.exact_post, similar_posts, errors = check_similarity(szuru, post.token)

    if errors:
        return False, False  # Assume the saucenao_limit_reached is False

    threshold = 1 - float(config.upload_media['max_similarity'])

    unique_media = not post.exact_post
    for entry in similar_posts:
        if entry['distance'] < threshold and unique_media:
            logger.debug(
                f'File "{file_path} is too similar to post {entry["post"]["id"]} ({100 - entry["distance"]}%)',
            )
            post.exact_post = entry
            unique_media = False
            break

    if unique_media:
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
        
        if not post.safety:
            post.safety = config.upload_media['default_safety']

        if post.tags == [] and config.upload_media['tags']:
            post.tags = config.upload_media['tags']

        post_id = upload_file(szuru, post)

        if not post_id:
            print()
            logger.warning(f'Error uploading post {post}.')
            return False, False

        # Tag post if enabled
        if config.upload_media['auto_tag']:
            saucenao_limit_reached = auto_tagger.main(
                post_id=str(post_id),
                file_to_upload=post.media,
                limit_reached=saucenao_limit_reached,
                md5=original_md5,
            )

    # If the exact post was found in szurubooru
    else:
        if config.import_from_url['update_tags_if_exists'] and metadata and ( metadata['tags'] or metadata['source'] or metadata['safety']):
            id = str(post.exact_post['id']) if 'id' in post.exact_post else str(post.exact_post['post']['id'])
           
            updated_post = szuru.get_posts(id, videos=True)
            discard = next(updated_post)
            updated_post = next(updated_post)
            if isinstance(updated_post, Post):
                prev_tags = updated_post.tags
                prev_source = updated_post.source
                prev_safety = updated_post.safety

                updated_post.tags = list(set().union(updated_post.tags, metadata['tags'])) if metadata['tags'] else updated_post.tags
                updated_post.source = add_urls_if_not_present(post.source, metadata['source']) if metadata['source'] else updated_post.source
                updated_post.safety = metadata['safety'] if metadata['safety'] else updated_post.safety

                if updated_post.tags != prev_tags or updated_post.source != prev_source or updated_post.safety != prev_safety:
                    szuru.update_post(updated_post)
            else:
                logger.warning(f"Expected a Post object but received a {type(updated_post)}: {updated_post}")

            
    return True, saucenao_limit_reached

def add_urls_if_not_present(main_string, additional_urls):
    if not additional_urls:
        return main_string
    #Check to seed if post.source is already empty
    if not main_string:
        return additional_urls

    additional_strings = additional_urls.split('\n')
    
    # Add each additional string to the main string if it's not already present
    for string in additional_strings:
        if string.strip() and string.strip() not in main_string:
            main_string += '\n' + string.strip()
    
    return main_string

def main(
    src_path: str = '',
    file_to_upload: bytes = None,
    file_ext: str = None,
    metadata: dict = None,
    saucenao_limit_reached: bool = False,
) -> bool:
    """
    Main logic of the script.

    This function is the entry point of the script. It takes a source path or a file to upload, and optionally a file
    extension and metadata. If no file to upload is provided, it will look for files in the source path. If no source
    path is provided, it will use the source path from the configuration. It then uploads each file found and returns
    whether the SauceNAO limit has been reached.

    Args:
        src_path (str, optional): The source path where to look for files to upload. Defaults to ''.
        file_to_upload (bytes, optional): A specific file to upload. Defaults to None.
        file_ext (str, optional): The file extension of the file to upload. Defaults to None.
        metadata (dict, optional): Metadata to attach to the post. Defaults to None.
        saucenao_limit_reached (bool, optional): If the SauceNAO limit has been reached. Defaults to False.

    Returns:
        bool: If the SauceNAO limit has been reached.

    Raises:
        KeyError: If no files are found to upload and no source path is specified.
    """

    try:
        if not file_to_upload:
            try:
                files_to_upload = src_path if src_path else get_files(config.upload_media['src_path'])
                called_externally = False
            except KeyError:
                logger.critical('No files found to upload. Please specify a source path.')
        else:
            files_to_upload = file_to_upload
            called_externally = True
            config.upload_media['hide_progress'] = True

        

        if files_to_upload:
            if not called_externally:
                logger.info('Found ' + str(len(files_to_upload)) + ' file(s). Starting upload...')

                try:
                    hide_progress = config.globals['hide_progress']
                except KeyError:
                    hide_progress = config.tag_posts['hide_progress']

                for file_path in tqdm(
                    files_to_upload,
                    ncols=80,
                    position=0,
                    leave=False,
                    disable=hide_progress,
                ):
                    if not os.path.isdir(file_path) and not file_path.endswith(('.txt', '.json')):
                        if os.path.exists(str(file_path) + '.json'):
                            with open(file_path + '.json') as json_file:
                                metadata = json.load(json_file)
                                metadata['site'] = get_site(metadata['file_url'])
                                metadata['source'] = metadata.get('source') + '\n' + metadata.get('file_url')

                                if 'rating' in metadata:
                                    metadata['safety'] = convert_rating(metadata['rating'])
                                else:
                                    metadata['safety'] = None

                                if 'tags' in metadata or 'tag_string' in metadata or 'hashtags' in metadata:
                                    metadata['tags'] = set_tags(metadata)
                                else:
                                    metadata['tags'] = []

                                # As Twitter doesn't provide any tags compared to other sources, we try to auto tag it.
                                if metadata['site'] == 'twitter':
                                    metadata['tags'] += extract_twitter_artist(metadata)
                                    config.auto_tagger['md5_search_enabled'] = True
                                    config.auto_tagger['saucenao_enabled'] = True
                                else:
                                    config.auto_tagger['md5_search_enabled'] = False
                                    config.auto_tagger['saucenao_enabled'] = False
                        elif os.path.exists(str(file_path) + '.txt'):
                            with open(str(file_path) + '.txt') as txt_file:
                                tags = txt_file.read().strip().replace(" ","_").splitlines()
                                metadata = {
                                    'safety': None,
                                    'tags': tags,
                                    'site': None,
                                    'source': None
                                }
                        else:
                            metadata = {
                                'safety': None,
                                'tags': [],
                                'site': None,
                                'source': None
                            }
                        with open(file_path, 'rb') as f:
                            file = f.read()

                        success, saucenao_limit_reached = upload_post(
                            file,
                            file_ext=Path(file_path).suffix[1:],
                            file_path=file_path,
                            metadata=metadata,
                            saucenao_limit_reached=saucenao_limit_reached,
                        )

                        if config.upload_media['cleanup'] and success:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            if os.path.exists(str(file) + '.json'):
                                os.remove(str(file) + '.json')
                            if os.path.exists(str(file) + '.txt'):
                                os.remove(str(file) + '.txt')

                if config.upload_media['cleanup']:
                    cleanup_dirs(config.upload_media['src_path'])  # Remove dirs after files have been deleted

                if not called_externally:
                    logger.success('Script has finished uploading!')

            else:
                _, saucenao_limit_reached = upload_post(file_to_upload, file_ext, metadata, saucenao_limit_reached=saucenao_limit_reached)

            return saucenao_limit_reached
        else:
            logger.info('No files found to upload.')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
