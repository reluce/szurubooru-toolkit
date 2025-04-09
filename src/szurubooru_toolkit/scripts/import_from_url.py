import glob
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit.pixiv import Pixiv
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import convert_tags
from szurubooru_toolkit.utils import extract_twitter_artist
from szurubooru_toolkit.utils import generate_src
from szurubooru_toolkit.utils import get_site
from szurubooru_toolkit.utils import invoke_gallery_dl
from szurubooru_toolkit.utils import sort_files


def set_tags(metadata: dict) -> list:
    """
    Processes the tags from the metadata of a post from various sites.

    This function checks if the site from the metadata is in the allowed list. If it is, it tries to convert the tags
    from the metadata into a list. If the site is 'fanbox', 'pixiv', or 'twitter', it uses the `convert_tags` function
    to convert the tags to known tags from Danbooru. If the site is not in the allowed list, it sets the tags to an
    empty list.

    For 'fanbox', 'pixiv', and 'e-hentai', it also tries to extract the artist's name from the metadata, tries to find
    the artist's name on Danbooru, and adds the artist's name to the list of tags if it exists.

    Args:
        metadata (dict): A dictionary containing the metadata of a post. It should have a 'site' key and may have
                         'tags', 'hashtags', 'tag_string', and 'user' keys.

    Returns:
        list: The processed list of tags. If the site is not in the allowed list or if an error occurs, it returns an
              empty list.
    """

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


def sort_file_by_time(file) -> datetime:
    """
    Sort a filepath collection by uploaded date from the accompanying JSON file,
    or alternatively by the file modification date.

    Returns:
        datetime: The uploaded date-time for the specified file.
    """
    filepath = Path(file)
    filepath_json = filepath.with_suffix(filepath.suffix + '.json')
    time_value = datetime.fromtimestamp(Path(filepath).stat().st_mtime)
    if filepath_json.exists():
        try:
            with open(filepath_json) as f:
                metadata = json.load(f)
                time_str = None
                if 'date' in metadata:
                    time_str = metadata['date']
                elif 'create_date' in metadata:
                    time_str = metadata['create_date']
                elif 'published' in metadata:
                    time_str = metadata['published']
                if time_str:
                    time_value = datetime.fromisoformat(time_str)
        except Exception:
            pass
    return time_value


@logger.catch
def main(urls: list = [], input_file: str = '', add_tags: list = [], verbose: bool = False) -> None:
    """
    Main function to handle the downloading of posts from URLs or an input file.

    This function first checks the configuration for various settings related to progress hiding and auto-tagging.
    Depending on these settings, it adjusts the configuration for the auto-tagger.

    It then checks if an input file is provided and whether URLs are also provided. Depending on the presence of these,
    it logs an appropriate message.

    The function then invokes gallery-dl to download the posts from the provided URLs or the URLs in the input file.
    For each downloaded post, it opens the associated JSON file to load the metadata. It sets the 'site' and 'source'
    keys in the metadata and converts the 'rating' key to a 'safety' key. If the metadata contains 'tags', 'tag_string',
    or 'hashtags', it sets the 'tags' key in the metadata to the result of the `set_tags` function. If not, it sets
    'tags' to an empty list. If the site is 'twitter', it also extracts the artist's name and adds it to the 'tags'.

    The function then opens the downloaded file and calls the `upload_media.main` function to upload the file and its
    metadata. If the SauceNAO limit is reached during the upload, it logs a message and continues with the next file.

    After all files have been processed, it removes the download directory and logs a success message.

    Args:
        urls (list, optional): A list of URLs from which to download posts. Defaults to an empty list.
        input_file (str, optional): A string representing the path to an input file containing URLs from which to
                                     download posts. Defaults to an empty string.
        add_tags (list, optional): A list of tags to add to the posts. Defaults to an empty list.
        verbose (bool, optional): A boolean indicating whether to log verbose messages. Defaults to False.

    Returns:
        None
    """

    try:
        hide_progress = config.globals['hide_progress']
    except KeyError:
        hide_progress = config.import_from_url['hide_progress']

    if any([config.import_from_url['deepbooru'], config.import_from_url['md5_search'], config.import_from_url['saucenao']]):
        config.upload_media['auto_tag'] = True

        if config.import_from_url['deepbooru']:
            config.auto_tagger['deepbooru'] = True
        else:
            config.auto_tagger['deepbooru'] = False
            config.auto_tagger['deepbooru_forced'] = False
        config.auto_tagger['md5_search'] = True if config.import_from_url['md5_search'] else False
        config.auto_tagger['saucenao'] = True if config.import_from_url['saucenao'] else False
    else:
        config.upload_media['auto_tag'] = False

    if input_file and not urls:
        logger.info(f'Downloading posts from input file "{input_file}"...')
    elif input_file and urls:
        logger.info(f'Downloading posts from input file "{input_file}" and URLs {urls}...')
    else:
        logger.info(f'Downloading posts from URLs {urls}...')
    params = [f'--range={config.import_from_url["range"]}', '--write-metadata']

    if config.import_from_url['cookies']:
        params += [f'--cookies={config.import_from_url["cookies"]}']

    if input_file:
        params += [f'--input-file={input_file}']

    if not verbose:
        params.append('-q')

    download_dir = invoke_gallery_dl(urls, config.import_from_url['tmp_path'], params)

    files = [
        file
        for file in glob.glob(f'{download_dir}/*')
        if Path(file).suffix not in ['.psd', '.json', '.zip', '.7z', '.rar', '.tar', '.gz', '.txt']
    ]
    files = sort_files(files)

    logger.info(f'Downloaded {len(files)} post(s). Start importing...')

    saucenao_limit_reached = False

    for file in tqdm(
        files,
        ncols=80,
        position=0,
        leave=False,
        disable=hide_progress,
    ):
        with open(file + '.json') as f:
            metadata = json.load(f)
            try:
                site = get_site(metadata['file_url'])
            except KeyError:
                site = get_site(metadata['category'])
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

            if site == 'twitter':
                metadata['tags'] += extract_twitter_artist(metadata)

            if add_tags:
                metadata['tags'] += add_tags

            with open(file, 'rb') as file_b:
                saucenao_limit_reached = upload_media.main(
                    file_to_upload=file_b.read(),
                    file_ext=Path(file).suffix[1:],
                    metadata=metadata,
                    saucenao_limit_reached=saucenao_limit_reached,
                )

    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)

    logger.success('Finished importing!')


if __name__ == '__main__':
    main()
