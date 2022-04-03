import sys

import bs4
import requests
from loguru import logger
from PIL import Image

from szurubooru_toolkit import Config


# Keep track of total tagged posts
total_tagged = 0
total_deepbooru = 0
total_untagged = 0
total_skipped = 0

# Increase the limit so DecompressionBomb warnings don't appear that often
Image.MAX_IMAGE_PIXELS = 100000000


def resize_image(local_image_path):
    with Image.open(local_image_path) as image:
        image = Image.open(local_image_path)
        image.thumbnail((1200, 1200))
        image.save(local_image_path)


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


def scrape_sankaku(sankaku_url):
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


def setup_logger(config: Config):
    """Setup loguru logging handlers."""

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
                colorize=True,
                level='INFO',
                filter=lambda record: record['level'].no < 30,
                format='<le>[{level}]</le> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg>: {message}',
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
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
