from __future__ import annotations

import hashlib
import re
import subprocess
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from datetime import datetime
from functools import total_ordering
from io import BytesIO
from pathlib import Path
from time import sleep

import httpx
from httpx import HTTPStatusError
from httpx import ReadTimeout
from loguru import logger
from PIL import Image

from szurubooru_toolkit import boorus
from szurubooru_toolkit.config import Config
from szurubooru_toolkit.pixiv import Pixiv
from szurubooru_toolkit.pixiv import PixivError


# Keep track of total tagged posts
total_tagged = 0
total_wd_tagger = 0
total_untagged = 0
total_skipped = 0
_statistics_lock = threading.Lock()


warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)
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


def resolve_onnx_providers(providers: list[str] | None) -> list[str]:
    """
    Validates the requested ONNX Runtime execution providers against the available ones.

    Unavailable providers are dropped with a warning; the CPU provider is always
    appended as fallback.

    Args:
        providers (list[str], optional): Execution providers in order of preference,
            e.g. ['CoreMLExecutionProvider'] on Apple Silicon or ['CUDAExecutionProvider']
            on NVIDIA GPUs.

    Returns:
        list[str]: The available providers, ending with the CPU provider.
    """

    import onnxruntime

    available = onnxruntime.get_available_providers()
    resolved = []

    for provider in providers or []:
        if provider == 'CPUExecutionProvider':
            continue
        if provider in available:
            resolved.append(provider)
        else:
            logger.warning(f'Requested ONNX execution provider "{provider}" is not available in this onnxruntime build.')

    resolved.append('CPUExecutionProvider')

    return resolved


def convert_rating(rating: str) -> str:
    """Map different ratings to szurubooru compatible rating.

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
        'g': 'safe',
        'general': 'safe',
        'Questionable': 'sketchy',
        'questionable': 'sketchy',
        'q': 'sketchy',
        'sensitive': 'sketchy',
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


SAFETY_LEVELS = {'safe': 0, 'sketchy': 1, 'unsafe': 2}


def apply_safety_overrides(tags: list, safety: str, overrides: dict) -> str:
    """
    Escalates a post's safety if any of the configured trigger tags are present.

    `overrides` maps a safety level to its trigger tags, e.g. {'sketchy': ['nude']}.
    Safety is only ever raised (safe < sketchy < unsafe), never lowered.

    Args:
        tags (list): The post's tags.
        safety (str): The post's current safety.
        overrides (dict): The safety_overrides mapping from the config.

    Returns:
        str: The (possibly escalated) safety.
    """

    tags = set(tags)

    for level, trigger_tags in overrides.items():
        if SAFETY_LEVELS[level] > SAFETY_LEVELS.get(safety, 0) and not tags.isdisjoint(trigger_tags):
            logger.debug(f'Escalating safety from {safety} to {level} (matched {tags.intersection(trigger_tags)})')
            safety = level

    return safety


def statistics(tagged=0, wd_tagger=0, untagged=0, skipped=0) -> tuple:
    """Keep track of how posts were tagged.

    Input values will get added to previously set value.

    Args:
        tagged (int, optional): If a post got its tags from SauceNAO. Defaults to 0.
        wd_tagger (int, optional): If a post was tagged with the WD tagger. Defaults to 0.
        untagged (int, optional): If a post was tagged neither with SauceNAO, nor the WD tagger. Defaults to 0.

    Returns:
        tuple: Returns the tracked progress (total_tagged, total_wd_tagger, total_untagged)
    """

    global total_tagged
    global total_wd_tagger
    global total_untagged
    global total_skipped

    with _statistics_lock:
        total_tagged += tagged
        total_wd_tagger += wd_tagger
        total_untagged += untagged
        total_skipped += skipped

        return total_tagged, total_wd_tagger, total_untagged, total_skipped


_implications_cache: dict[str, list[str]] = {}
_implications_lock = threading.Lock()


def get_cached_implications(tag_name: str, create_missing: bool = False) -> list[str]:
    """
    Returns the implication names of a tag, cached across posts.

    Tag implications rarely change during a run, so fetching them once per tag
    instead of once per post removes an N+1 query pattern.

    Args:
        tag_name (str): The tag whose implications to fetch.
        create_missing (bool, optional): Create the tag if it doesn't exist. Defaults to False.

    Returns:
        list[str]: The primary names of the tag's implications.

    Raises:
        TagNotFoundError: If the tag doesn't exist and create_missing is False.
    """

    from szurubooru_toolkit import szuru
    from szurubooru_toolkit.szurubooru import TagNotFoundError

    with _implications_lock:
        if tag_name in _implications_cache:
            return _implications_cache[tag_name]

    try:
        szuru_tag = szuru.get_tag(tag_name)
    except TagNotFoundError:
        if not create_missing:
            raise
        szuru_tag = szuru.create_tag(tag_name)

    implications = [implication.primary_name for implication in szuru_tag.implications]

    with _implications_lock:
        _implications_cache[tag_name] = implications

    return implications


def run_concurrently(items, worker, workers: int, total: int, hide_progress: bool) -> None:
    """
    Runs the worker over all items on a thread pool, showing progress.

    Worker errors are logged per item and don't abort the remaining items. With
    workers <= 1 the items are processed sequentially without a pool.

    Args:
        items: Iterable of items to process (may be a generator).
        worker: Callable invoked with a single item.
        workers (int): Number of concurrent workers.
        total (int): Total number of items, for the progress bar.
        hide_progress (bool): Whether to hide the progress bar.

    Returns:
        None
    """

    from tqdm import tqdm

    def safe_worker(item) -> None:
        try:
            worker(item)
        except Exception as e:
            logger.error(f'Could not process {item}: {e}')

    if workers <= 1:
        for item in tqdm(items, ncols=80, position=0, leave=False, total=total, disable=hide_progress):
            safe_worker(item)
        return

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [executor.submit(safe_worker, item) for item in items]
        for _ in tqdm(as_completed(futures), ncols=80, position=0, leave=False, total=total, disable=hide_progress):
            pass
    except KeyboardInterrupt:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    executor.shutdown()


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
    """Replace whitespaces in tags with underscores.

    Returns an empty list if tags is an empty list.

    Args:
        tags (list): A list of tags.

    Returns:
        list: A list of sanitized tags.

    Example:
        sanitize_tags(['tag1', 'tag 2']) -> ['tag1', 'tag_2']
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


def get_md5sum(file: bytes) -> str:
    """
    Calculates the MD5 checksum of the provided file.

    This function calculates the MD5 checksum of the provided file. It uses the hashlib.md5 function to calculate the
    checksum and then converts the result to a hexadecimal string. It returns the hexadecimal string.

    Args:
        file (bytes): The file for which to calculate the MD5 checksum.

    Returns:
        str: The MD5 checksum of the file.
    """

    md5sum = hashlib.md5(file).hexdigest()

    return md5sum


def download_media(content_url: str, md5: str = None) -> bytes | None:
    """
    Downloads media from the specified content URL, verifying its MD5 checksum.

    Tries up to two times. If an MD5 checksum is provided and the downloaded content
    doesn't match it, the download is retried once; the last downloaded content is
    returned even on a checksum mismatch.

    Args:
        content_url (str): The URL from which to download the media.
        md5 (str, optional): The MD5 checksum to verify. Defaults to None.

    Returns:
        bytes | None: The downloaded media, or None if both attempts failed.
    """

    file = None

    for _ in range(2):
        try:
            file = httpx.get(content_url, follow_redirects=True, timeout=30).content
        except Exception as e:
            logger.warning(f'Could not download post from {content_url}: {e}')
            continue

        if not md5 or get_md5sum(file) == md5:
            break

    return file


def generate_src(metadata: dict) -> str:
    """
    Generates the source URL for a post based on its metadata.

    This function generates the source URL for a post based on its metadata. It first checks if the metadata contains
    an 'id' key and, if so, stores the value in a variable. It then uses a match statement to determine the site from
    which the post originates. Depending on the site, it constructs the source URL in a different way. If the site is
    not recognized, it sets the source URL to None. If a KeyError occurs while constructing the source URL, it catches
    the exception and continues.

    Args:
        metadata (dict): The metadata from which to generate the source URL.

    Returns:
        str: The source URL for the post, or None if the site is not recognized.
    """

    if 'id' in metadata:
        id = str(metadata['id'])

    try:
        match metadata['site']:
            case 'danbooru' | 'donmai':
                src = 'https://danbooru.donmai.us/posts/' + id
            case 'e-hentai':
                id = str(metadata['gid'])
                token = metadata['token']
                src = f'https://e-hentai.org/g/{id}/{token}'
            case 'gelbooru':
                src = 'https://gelbooru.com/index.php?page=post&s=view&id=' + id
            case 'konachan':
                src = 'https://konachan.com/post/show/' + id
            case 'sankaku':
                src = 'https://sankakucomplex.com/posts/' + id
            case 'yandere':
                src = 'https://yande.re/post/show/' + id
            case 'twitter':
                user = metadata['author']['name']
                id = str(metadata['tweet_id'])
                src = f'https://twitter.com/{user}/status/{id}'
            case 'kemono':
                user = metadata['user']
                service = metadata['service']
                src = f'https://kemono.party/{service}/user/{user}/post/{id}'
            case 'fanbox':
                user = metadata['creatorId']
                src = f'https://fanbox.cc/@{user}/posts/{id}'
            case 'pixiv':
                src = 'https://www.pixiv.net/artworks/' + id
            case _:
                src = None
    except KeyError:
        src = None

    return src


def _search_single_booru(booru: str, query: str, limit: int, page: int, credentials: dict[str, dict]) -> list | None:
    """
    Searches one booru with retries; returns the results or None.
    """

    max_attempts = 11

    for attempt in range(1, max_attempts + 1):
        try:
            if booru == 'sankaku':
                from szurubooru_toolkit import sankaku

                return sankaku.search(query, limit, page)
            elif booru in credentials:
                return boorus.search(booru, query, limit, page, credentials=credentials[booru])
            # Search Gelbooru only if credentials are provided
            # Otherwise the rate limits are too harsh
            elif booru == 'gelbooru':
                logger.debug('Skipping Gelbooru as no credentials were provided.')
                return None
            else:
                return boorus.search(booru, query, limit, page)
        except KeyError:
            logger.debug(f'No result found in {booru} with "{query}"')
            return None
        except HTTPStatusError as e:
            logger.debug(e)
            if e.response.status_code in [401, 403]:
                logger.warning(f'Invalid credentials or unauthorized for {booru}.')
                return None
            logger.debug(f'Could not establish connection to {booru}. Trying again in 5s...')
            if attempt < max_attempts:  # no need to sleep on the last attempt
                sleep(5)
        except ReadTimeout:
            logger.debug(f'Could not establish connection to {booru}. Trying again in 5s...')
            if attempt < max_attempts:  # no need to sleep on the last attempt
                sleep(5)
        except Exception as e:
            logger.debug(f'Could not get result from {booru} with "{query}": {e}. Trying again. in 5s...')
            if attempt < max_attempts:  # no need to sleep on the last attempt
                sleep(5)

    logger.debug(f'Could not establish connection to {booru}, trying with next post...')
    statistics(skipped=1)
    return None


def search_boorus(booru: str, query: str, limit: int, page: int = 1, credentials: dict[str, dict] = {}) -> dict:
    """
    Searches the specified Boorus for the given query.

    All requested boorus are queried concurrently, so the call takes as long as the
    slowest booru instead of the sum of all of them. Each booru is retried on
    connection errors before giving up on it.

    Args:
        booru (str): The Booru or Boorus to search. If 'all', it searches all Boorus.
        query (str): The query to search for.
        limit (int): The maximum number of results to return.
        page (int, optional): The page of results to return. Defaults to 1.
        credentials (dict[str, dict[str, str | None]], optional): HTTP Parameters for Authentication. Defaults to empty dict.

    Returns:
        dict: The search results, with the Booru as the key and the results as the value.
    """

    boorus_to_search = ['sankaku', 'danbooru', 'gelbooru', 'konachan', 'yandere'] if booru == 'all' else [booru]

    if len(boorus_to_search) == 1:
        name = boorus_to_search[0]
        result = _search_single_booru(name, query, limit, page, credentials)
        return {name: result} if result else {}

    results = {}
    with ThreadPoolExecutor(max_workers=len(boorus_to_search)) as executor:
        futures = {executor.submit(_search_single_booru, name, query, limit, page, credentials): name for name in boorus_to_search}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results[futures[future]] = result

    return results


def convert_tags(tags: list) -> list:
    """
    Search for tags that don't follow the Booru convention in Danbooru and convert them.

    Args:
        tags (list): The tags to convert.

    Returns:
        list: The converted tags.
    """

    from szurubooru_toolkit import danbooru

    unfiltered_tags = []

    for tag in tags:
        unfiltered_tags.append(danbooru.get_other_names_tag(tag))

    filtered_tags = [tag for tag in unfiltered_tags if tag is not None]

    return filtered_tags


def prepare_post(results: dict, config: Config) -> tuple[list[str], list[str], str]:
    """
    Prepares a post for upload to szurubooru.

    This function prepares a post for upload to szurubooru. It extracts the tags, sources, and rating from the results
    and config. It checks each booru in the results and adds the tags, source, and rating to their respective lists. If
    the booru is Pixiv and a token is provided, it gets the result from Pixiv and adds the tags and rating. If no tags
    are found and the configuration is set to use Pixiv tags, it uses the Pixiv tags. It also extracts the Pixiv artist
    and adds it to the tags. It then flattens the tags list and returns the tags, sources, and rating.

    Args:
        results (dict): The results from which to extract the tags, sources, and rating.
        config (Config): The configuration from which to extract the Pixiv token and whether to use Pixiv tags.

    Returns:
        Tuple[List[str], List[str], str]: The tags, sources, and rating for the post.
    """

    tags = []
    sources = []
    rating = []
    booru_found = False
    pixiv_rating = None
    pixiv_artist = None
    for booru, result in results.items():
        if booru != 'pixiv':
            if booru == 'sankaku':
                tags.append([tag['tagName'] for tag in result[0]['tags']])
                sources.append(generate_src({'site': booru, 'id': result[0]['id']}))
                rating = convert_rating(result[0]['rating'])
            else:
                tags.append(result[0].tags.split())
                sources.append(generate_src({'site': booru, 'id': result[0].id}))
                rating = convert_rating(result[0].rating)
            booru_found = True
        else:
            pixiv_tags = None
            if config.credentials['pixiv']['token']:
                try:
                    pixiv = Pixiv(config.credentials['pixiv']['token'])
                    pixiv_result = pixiv.get_result(results['pixiv'].url)
                    if pixiv_result:
                        pixiv_tags = pixiv.get_tags(pixiv_result)
                        tags.append(convert_tags(pixiv_tags))
                        pixiv_rating = pixiv.get_rating(pixiv_result)
                    else:
                        pixiv_rating = None
                except ImportError as e:
                    logger.warning(f'{e} Skipping Pixiv metadata...')
                    pixiv_rating = None
                except PixivError as e:
                    logger.warning(f'Could not get result from pixiv: {e}')
                    pixiv_rating = None

            if not tags and pixiv_tags and config.auto_tagger['use_pixiv_tags']:
                tags = pixiv_tags

            sources.append(results['pixiv'].url)
            pixiv_artist = Pixiv.extract_pixiv_artist(results['pixiv'].author_name)
            if pixiv_artist:
                tags.append([pixiv_artist])

    final_tags = [item for sublist in tags for item in sublist]

    if not booru_found and pixiv_rating:
        rating = pixiv_rating

    if not booru_found and pixiv_artist:
        final_tags.append(pixiv_artist)

    return final_tags, sources, rating


def invoke_gallery_dl(urls: list, tmp_path: str, params: list = [], workers: int = 1) -> str:
    """
    Invokes gallery-dl for the provided URLs and parameters.

    All downloads end up in a shared timestamped directory below `tmp_path`. When
    multiple URLs are given, one gallery-dl process is started per URL and up to
    `workers` of them run concurrently, since gallery-dl itself downloads
    sequentially. A single URL (or an input file passed via params) runs as one
    process.

    Args:
        urls (list): The URLs to download.
        tmp_path (str): The temporary path where the downloads should be stored.
        params (list, optional): The parameters to pass to the gallery-dl command. Defaults to [].
        workers (int, optional): How many gallery-dl processes to run concurrently. Defaults to 1.

    Returns:
        str: The download directory.
    """

    current_time = datetime.now()
    timestamp = current_time.timestamp()
    download_dir = f'{tmp_path}/{timestamp}'
    base_command = ['gallery-dl', f'-D={download_dir}'] + params

    if len(urls) > 1 and workers > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(urls))) as executor:
            futures = [executor.submit(subprocess.run, base_command + [url]) for url in urls]
            for future in futures:
                future.result()
    else:
        subprocess.run(base_command + urls)

    return download_dir


def extract_twitter_artist(metadata: dict) -> str | None:
    """
    Extracts the Twitter artist from the metadata.

    This function extracts the Twitter artist from the metadata. It first tries to find the artist by their Twitter
    name in Danbooru. If it cannot find the artist, it tries to find the artist by their Twitter nickname. If it still
    cannot find the artist and the configuration is set to use the Twitter artist, it creates a new artist tag in
    szurubooru with the Twitter name and nickname as aliases. If an error occurs while creating the tag, it logs the
    error and continues. It returns the artist if it exists, otherwise it returns the aliases.

    Args:
        metadata (dict): The metadata from which to extract the Twitter artist.

    Returns:
        str: The artist if it exists, otherwise the aliases.
        None: If the artist cannot be found.
    """

    from szurubooru_toolkit import config
    from szurubooru_toolkit import danbooru
    from szurubooru_toolkit import szuru

    twitter_name = metadata['author']['name']
    twitter_nick = metadata['author']['nick']
    artist_aliases = None

    artist = danbooru.search_artist(twitter_name)
    if not artist:
        artist = danbooru.search_artist(twitter_nick)

    if not artist and config.import_from_url['use_twitter_artist']:
        artist_aliases = [twitter_name.lower().replace(' ', '_')]
        artist_aliases.append(twitter_nick.lower().replace(' ', '_').replace('\u3000', ''))
        for artist_alias in artist_aliases:
            try:
                szuru.create_tag(artist_alias, category='artist', overwrite=True)
            except Exception as e:
                logger.debug(f'Could not create Twitter artist {artist_alias}: {e}')

    return [artist] if not artist_aliases else artist_aliases


def get_site(url: str) -> str:
    """
    Extracts the site name from a given URL.

    Args:
        url (str): The URL to extract the site name from.

    Returns:
        str: The name of the site that the URL belongs to, or None if no known site name is found in the URL.
    """

    sites = {
        'sankaku',
        'danbooru',
        'gelbooru',
        'konachan',
        'yandere',
        'e-hentai',
        'twitter',
        'kemono',
        'fanbox',
        'pixiv',
    }

    # gallery-dl reports category 'exhentai' for both e-hentai.org and
    # exhentai.org; the toolkit handles both under 'e-hentai'.
    if 'exhentai' in url:
        return 'e-hentai'

    # Danbooru serves files from cdn.donmai.us; the toolkit handles it as 'danbooru'.
    if 'donmai' in url:
        return 'danbooru'

    for site in sites:
        if site in url:
            return site


@total_ordering
class FileInfo:
    """A class that handles file sorting with timestamp and natural ordering.

    This class provides functionality to sort files first by their timestamp and then
    by their names using natural sorting (e.g., "file2.jpg" comes before "file10.jpg").
    It implements rich comparison methods through the @total_ordering decorator.

    Attributes:
        filepath: A string containing the path to the file.
        timestamp: A datetime object representing the file's modification time.
        natural_keys: A list of strings and integers representing the filename broken
            into natural sorting components.
    """

    def __init__(self, filepath: str) -> None:
        """Initialize a FileInfo instance.

        Args:
            filepath: A string containing the path to the file.
        """

        self.filepath = filepath
        self.timestamp = self._get_file_time()
        self.natural_keys = self._natural_keys(filepath)

    def _get_file_time(self) -> datetime:
        """Get the file's timestamp using various fallback methods.

        Attempts to get the file's modification time (mtime) first, then creation
        time (ctime) if mtime fails. Falls back to current time if both fail.

        Returns:
            datetime: The timestamp of the file.
        """

        time_value = datetime.now()  # Default fallback
        path = Path(self.filepath)

        try:
            time_value = datetime.fromtimestamp(path.stat().st_mtime)
        except (OSError, AttributeError):
            try:
                time_value = datetime.fromtimestamp(path.stat().st_ctime)
            except (OSError, AttributeError):
                pass
        return time_value

    @staticmethod
    def _atoi(text: str) -> int | str:
        """Convert string to integer if possible.

        Args:
            text: String that might represent an integer.

        Returns:
            Either an int if the text represents a number, or the original string.
        """

        return int(text) if text.isdigit() else text

    def _natural_keys(self, text: str) -> list[int | str]:
        """Split string into a list of string and number chunks.

        This is the key to natural sorting. It splits a string into chunks
        that can be naturally compared (e.g., ["file", 2] vs ["file", 10]).

        Args:
            text: String to be split into natural keys.

        Returns:
            A list where numeric chunks are converted to int and others remain str.

        Example:
            >>> self._natural_keys("file123test456")
            ['file', 123, 'test', 456]
        """

        return [self._atoi(c) for c in re.split(r'(\d+)', text)]

    def __eq__(self, other: FileInfo) -> bool:
        """Check if two FileInfo objects are equal.

        Two files are considered equal if they have the same timestamp and
        natural keys.

        Args:
            other: Another FileInfo instance to compare with.

        Returns:
            bool: True if the files are equal, False otherwise.
        """

        if not isinstance(other, FileInfo):
            return NotImplemented
        return (self.timestamp, self.natural_keys) == (other.timestamp, other.natural_keys)

    def __lt__(self, other: FileInfo) -> bool:
        """Compare if this file should come before another file.

        The comparison is done first by timestamp, then by natural sort of names
        if timestamps are equal.

        Args:
            other: Another FileInfo instance to compare with.

        Returns:
            bool: True if this file should come before the other file, False otherwise.
        """

        if not isinstance(other, FileInfo):
            return NotImplemented
        return (self.timestamp, self.natural_keys) < (other.timestamp, other.natural_keys)


def sort_files(files: list[str]) -> list[str]:
    """Sort files by timestamp and natural ordering of names.

    This function implements a two-level sorting:
    1. First by file timestamp (modification time)
    2. Then by natural sort of filenames (so file2.jpg comes before file10.jpg)

    Args:
        files: A list of file paths to sort.

    Returns:
        A new list containing the file paths sorted by timestamp and name.

    Example:
        >>> files = ['file10.jpg', 'file2.jpg']
        >>> sort_files(files)
        ['file2.jpg', 'file10.jpg']

    Note:
        This function uses the FileInfo class internally to handle the sorting
        logic. The sorting is stable, meaning files with the same timestamp
        will maintain their relative order based on filename.
    """

    return sorted(files, key=FileInfo)
