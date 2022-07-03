from __future__ import annotations

import hashlib
import sys
import warnings
from io import BytesIO
from math import ceil
from typing import Iterator
from urllib.error import ContentTooShortError

import bs4
import requests
from loguru import logger
from lxml import etree
from PIL import Image
from pybooru import Moebooru
from pybooru.exceptions import PybooruHTTPError
from pygelbooru.gelbooru import GelbooruImage
from syncer import sync

from szurubooru_toolkit import Config
from szurubooru_toolkit import Danbooru
from szurubooru_toolkit import Gelbooru


# Keep track of total tagged posts
total_tagged = 0
total_deepbooru = 0
total_untagged = 0
total_skipped = 0

warnings.simplefilter('error', Image.DecompressionBombWarning)
warnings.filterwarnings('ignore', '.*Palette images with Transparency.*', module='PIL')


def shrink_img(
    tmp_file: bytes,
    resize: bool = False,
    shrink_threshold: int = None,
    shrink_dimensions: tuple = None,
    convert: bool = False,
    convert_quality: int = 75,
) -> bytes:
    """Try to shrink the file size of the given `tmp_file`.

    The image will get saved to the `tmp_path`.

    Shrinking measures include to set its max height/width to 1000px (maybe still too high) and to
    optionally convert it to a JPG file while trying to optimize it (mostly quality 75 setting).

    Args:
        tmp_file (bytes): The image as bytes which should be shrunk.
        shrink_threshold (int): Total pixel count which has to be breached in order to shrink the image.
        shrink_dimensions (tuple): Image will be resized to the higher element. Will keep aspect ratio.
            First element is the max width, second the max height.
        resize (bool, optional): If the image should be resized to max height/width of 1000px. Defaults to False.
        convert (bool, optional): If the image should be converted to JPG format. Defaults to False.
        convert_quality (int): Set up to 95. Higher means better quality, but takes up more disk space.

    Returns:
        bytes: The image in bytes.
    """

    with Image.open(BytesIO(tmp_file)) as img:
        total_pixel = img.width * img.height
        buffer = BytesIO()  # Image will get saved to this buffer
        shrunk = False

        if resize:
            img.thumbnail((1000, 1000))
            shrunk = True

        if shrink_threshold:
            if total_pixel > shrink_threshold:
                img.thumbnail(shrink_dimensions)
                shrunk = True

        if convert:
            img.convert('RGB').save(buffer, format='JPEG', optimize=True, quality=convert_quality)
            image = buffer.getvalue()
        elif shrunk:
            img.save(buffer, format=img.format)
            image = buffer.getvalue()
        else:
            image = tmp_file

    return image


def convert_rating(rating: str) -> str:
    """Map different ratings to szuru compatible rating.

    Args:
        rating (str): The rating you want to convert

    Returns:
        str: The szuru compatible rating

    Example:
        convert_rating('rating:safe') -> 'safe'
    """
    switch = {
        'Safe': 'safe',
        'safe': 'safe',
        's': 'safe',
        'Questionable': 'sketchy',
        'questionable': 'sketchy',
        'q': 'sketchy',
        'Explicit': 'unsafe',
        'explicit': 'unsafe',
        'e': 'unsafe',
        'rating:safe': 'safe',
        'rating:questionable': 'sketchy',
        'rating:explicit': 'unsafe',
    }

    new_rating = switch.get(rating)
    logger.debug(f'Converted rating {rating} to {new_rating}')

    return new_rating


def scrape_sankaku(sankaku_url: str) -> tuple[list, str]:
    """Scrape the tags and rating from given `sankaku_url`.

    Args:
        sankaku_url (str): The Sankaku URL of the post.

    Returns:
        Tuple[list, str]: Contains `tags` as a `list` and `rating` as `str` of the post.
    """

    response = requests.get(sankaku_url)
    result_page = bs4.BeautifulSoup(response.text, 'html.parser')

    rating_raw = str(result_page.select('#stats li'))
    rating_sankaku = rating_raw.partition('Rating: ')[2]
    rating_sankaku = rating_sankaku.replace('</li>]', '')
    rating = convert_rating(rating_sankaku)

    tags_raw = str(result_page.title.string)
    tags = tags_raw.replace(' | Sankaku Channel', '')
    tags = tags.replace(' ', '_')
    tags = tags.replace(',_', ' ')

    tags = tags.split()

    return tags, rating


def statistics(tagged=0, deepbooru=0, untagged=0, skipped=0) -> tuple:
    """Keep track of how posts were tagged.

    Input values will get added to previously set value.

    Args:
        tagged (int, optional): If a post got its tags from SauceNAO. Defaults to 0.
        deepbooru (int, optional): If a post was tagged with Deepbooru. Defaults to 0.
        untagged (int, optional): If a post was tagged neither with SauceNAO, nor Deepbooru. Defaults to 0.

    Returns:
        tuple: Returns the tracked progress (total_tagged, total_deepbooru, total_untagged)
    """

    global total_tagged
    global total_deepbooru
    global total_untagged
    global total_skipped

    total_tagged += tagged
    total_deepbooru += deepbooru
    total_untagged += untagged
    total_skipped += skipped

    return total_tagged, total_deepbooru, total_untagged, total_skipped


def audit_rating(*ratings: str) -> str:
    """Return the highest among the scraped input ratings.

    Ranges from safe (0) to unsafe (1).
    Returns 'safe' if ratings is an empty list.

    Args:
        *ratings (str): Each input rating as a str.

    Returns:
        str: The highest scraped rating.

    Example:
        audit_rating('sketchy', 'unsafe') -> 'unsafe'
    """

    verdict = 'safe'
    weight = {'unsafe': 2, 'sketchy': 1, 'safe': 0}

    for r in ratings:
        if not r:
            continue
        if weight[r] > weight[verdict]:
            verdict = r

    return verdict


def sanitize_tags(tags: list) -> list:
    """Collect tags, remove duplicates and replace whitespaces with underscores.

    Retuns an empty list if tags is an empty list.

    Args:
        tags (list): A list of tags.

    Returns:
        list: A list of sanitized tag.

    Example:
        sanitize_tags(['tag1', 'tag 2', 'tag1']) -> ['tag1', 'tag_2']
    """

    tags_sanitized = []

    for tag in tags:
        tag = tag.replace(' ', '_')
        tags_sanitized.append(tag)

    return tags_sanitized


def collect_sources(*sources: str) -> str:
    """Collect sources in a single string separated by a newline char.

    Removes duplicate sources as well.
    Returns an empty string if sources is an empty list.

    Args:
        *sources (str): Each input source as a str.

    Returns:
        str: Every input source in a single str, separated by a newline char.

    Example:
        collect_sources('foo', 'bar', foo') -> 'foo\nbar'
    """

    # Remove empty sources
    source_valid = [source for source in sources if source]

    # Remove ','
    sources_sanitized = []
    for source in source_valid:
        if source[-1] == ',':
            source = source[:-1]
        sources_sanitized.append(source)

    # Remove duplicates
    source_valid = list(set(sources_sanitized))

    delimiter = '\n'
    source_collected = delimiter.join(source_valid)
    return source_collected


def setup_logger(config: Config) -> None:
    """Setup loguru logging handlers.

    Args:
        config (Config): Config object with user configuration from `config.toml`.
    """

    logger.configure(
        handlers=[
            dict(
                sink=config.logging['log_file'],
                colorize=config.logging['log_colorized'],
                level=config.logging['log_level'],
                diagnose=False,
                format=''.join(
                    '<lm>[{level}]</lm> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg> '
                    '<ly>[{module}.{function}]</ly>: {message}',
                ),
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='INFO',
                filter=lambda record: record['level'].no < 30,
                format='<le>[{level}]</le> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg>: {message}',
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='WARNING',
                filter=lambda record: record['level'].no < 40,
                format=''.join(
                    '<ly>[{level}]</ly> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg> '
                    '<ly>[{module}.{function}]</ly>: {message}',
                ),
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='ERROR',
                format=''.join(
                    '<lr>[{level}]</lr> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg> '
                    '<ly>[{module}.{function}]</ly>: {message}',
                ),
            ),
        ],
    )

    if not config.logging['log_enabled']:
        logger.remove(2)  # Assume id 2 is the handler with the log file sink


def get_md5sum(file: bytes) -> str:
    """Retrieve and return the MD5 checksum from supplied `file`.

    Args:
        file (bytes): The file as a byte string.

    Returns:
        str: The calculated MD5 checksum.
    """

    md5sum = hashlib.md5(file).hexdigest()

    return md5sum


def download_media(content_url: str, md5: str = None) -> bytes:
    """Download the file from `content_url` and return it if the md5 hashes match.

    Args:
        content_url (str): The URL of the file to download.
        md5 (str): The expected md5 hash of the file.

    Returns:
        bytes: The downloaded file as a byte string.
    """

    for _ in range(1, 3):
        try:
            file: bytes = requests.get(content_url).content
        except ContentTooShortError:
            download_media(content_url, md5)
        except Exception as e:
            print('')
            logger.warning(f'Could not download post from {content_url}: {e}')

        if md5:
            md5sum = get_md5sum(file)

            if md5 == md5sum:
                break
        else:
            break

    return file


def get_posts_from_booru(
    booru: Danbooru | Gelbooru | Moebooru,
    query: str,
    limit: int,
) -> Iterator[int | dict | GelbooruImage]:
    """Retrieve posts from Boorus based on search query and yields them.

    Args:
        booru (Danbooru | Gelbooru | Moebooru): Booru object
        query (str): The search query which results will be retrieved.
        limit (int): The search limit. If not set, use defaults from module (100).

    Yields:
        Iterator[int | dict | GelbooruImage]: Yields the total count of posts first,
            then either a GelbooruImage or a dict for the other Boorus.
    """

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
