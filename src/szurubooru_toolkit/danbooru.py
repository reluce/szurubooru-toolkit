from functools import lru_cache
from math import ceil
from threading import Lock
from time import monotonic
from time import sleep
from typing import List
from typing import Optional

import httpx
from loguru import logger

from szurubooru_toolkit.boorus import USER_AGENT

# 429 is a short throttle and worth retrying. 5xx (including Cloudflare's
# "Downbooru" 503) means the site is down: fail the lookup and skip further
# requests for Retry-After seconds instead of blocking the import 5s at a time.
_RATE_LIMITED = 429
_OUTAGE_STATUS_CODES = {401, 403, 500, 502, 503, 504}
_RATE_LIMIT_RETRIES = 3


class _Unavailable(Exception):
    """Danbooru is down or blocked; remaining lookups should be skipped."""


def _retry_after(response: httpx.Response, default: float) -> float:
    value = response.headers.get('Retry-After')
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return default


class Danbooru:
    """Handles the Danbooru API calls the toolkit needs (artists, wiki pages, tag export)."""

    def __init__(self, transport: httpx.BaseTransport = None) -> None:
        """
        Initialize the Danbooru client with a pooled httpx session.

        Args:
            transport (httpx.BaseTransport, optional): Custom transport, used for testing.
        """

        self.client = httpx.Client(
            base_url='https://danbooru.donmai.us',
            headers={'User-Agent': USER_AGENT},
            timeout=30,
            follow_redirects=True,
            transport=transport,
        )
        self._lock = Lock()
        self._skip_until = 0.0
        self._skip_logged = False

    def _available(self) -> bool:
        # Respect the per-run skip from the post search, otherwise every expired window retries a dead site
        from szurubooru_toolkit import utils

        if utils.booru_skipped('danbooru'):
            return False

        with self._lock:
            if monotonic() < self._skip_until:
                return False
            self._skip_logged = False
            return True

    def _mark_down(self, seconds: float, reason: str) -> None:
        with self._lock:
            self._skip_until = max(self._skip_until, monotonic() + seconds)
            if not self._skip_logged:
                logger.warning(f'{reason}; skipping Danbooru lookups for {int(seconds)}s')
                self._skip_logged = True

    def _get_json(self, path: str, params: dict) -> object:
        """GET JSON from Danbooru, retrying 429s. Outages open a skip window."""

        if not self._available():
            raise _Unavailable

        for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
            try:
                response = self.client.get(path, params=params)
            except (TimeoutError, httpx.TransportError) as e:
                if attempt == _RATE_LIMIT_RETRIES:
                    self._mark_down(30, f'Danbooru unreachable ({e})')
                    raise _Unavailable from e
                logger.debug(f'Danbooru {path} failed ({e}), retrying in 5s...')
                sleep(5)
                continue

            if response.status_code == _RATE_LIMITED:
                wait = _retry_after(response, 5 * attempt)
                if attempt == _RATE_LIMIT_RETRIES:
                    self._mark_down(wait, 'Danbooru rate limited (HTTP 429)')
                    raise _Unavailable
                logger.debug(f'Danbooru {path} HTTP 429, retrying in {wait}s...')
                sleep(wait)
                continue

            if response.status_code in _OUTAGE_STATUS_CODES:
                wait = _retry_after(response, 30)
                self._mark_down(wait, f'Danbooru returned HTTP {response.status_code}')
                raise _Unavailable

            response.raise_for_status()
            return response.json()

    def get_other_names_tag(self, other_tag: str) -> Optional[str]:
        """
        Search for the main tag name of the given tag.

        Cached per run. An outage is not cached as "missing" so a later recovery
        can still resolve the tag.

        Args:
            other_tag (str): The tag you want to search for.

        Returns:
            Optional[str]: The main tag if found, None otherwise.
        """

        if not self._available():
            return None
        try:
            return self._get_other_names_tag(other_tag)
        except _Unavailable:
            return None

    # Cached per run: imports and pixiv results look up the same tags and artists over and over
    @lru_cache(maxsize=4096)
    def _get_other_names_tag(self, other_tag: str) -> Optional[str]:
        try:
            pages = self._get_json('/wiki_pages.json', {'search[other_names_match]': other_tag, 'only': 'title'})
            tag = pages[0]['title']
        except (IndexError, KeyError, TypeError, ValueError):
            logger.debug(f'Could not find tag for other_tag "{other_tag}"')
            return None
        except httpx.HTTPStatusError as e:
            logger.debug(f'Could not look up tag "{other_tag}": {e}')
            return None

        logger.debug(f'Returning found tag for {other_tag}: {tag}')
        return tag

    def search_artist(self, artist: str) -> Optional[str]:
        """
        Search for the main artist name on Danbooru and return it.

        Looks up the artist first by base name, then by other names. Cached per
        run; an outage is not cached as "missing".

        Args:
            artist (str): The artist name. Can be an alias as well.

        Returns:
            Optional[str]: The main artist name if found, None otherwise.
        """

        if not self._available():
            return None
        try:
            return self._search_artist(artist)
        except _Unavailable:
            return None

    @lru_cache(maxsize=4096)
    def _search_artist(self, artist: str) -> Optional[str]:
        try:
            result = self._get_json('/artists.json', {'search[name]': artist.lower()})
            if result:
                name = result[0]['name']
            else:
                params = {'search[any_other_name_like]': artist.lower(), 'search[is_deleted]': 'false'}
                name = self._get_json('/artists.json', params)[0]['name']
        except (IndexError, KeyError, TypeError, ValueError):
            logger.debug(f'Could not find artist "{artist.lower()}"')
            return None
        except httpx.HTTPStatusError as e:
            logger.debug(f'Could not look up artist "{artist}": {e}')
            return None

        logger.debug(f'Returning artist: {name}')
        return name

    def download_tags(self, query: str = '*', min_post_count: int = 10, limit: int = 100) -> List[dict]:
        """
        Download and return tags from Danbooru.

        This method downloads tags from Danbooru. It builds the request with the provided query, minimum post count,
        and limit, and yields the tags page by page.

        Args:
            query (str, optional): Search for specific tag, accepts wildcard (*). If not specified, download all tags.
                                Defaults to '*'.
            min_post_count (int, optional): The minimum amount of posts the tag should have been used in. Defaults to 10.
            limit (int, optional): The amount of tags that should be downloaded. Start from the most recent ones.
                                Defaults to 100.

        Yields:
            List[dict]: A page of found tags.
        """

        # Danbooru returns at most 1000 tags per page
        pages = max(1, ceil(limit / 1000))

        for page in range(1, pages + 1):
            params = {
                'search[post_count]': f'>={min_post_count}',
                'search[name_matches]': query,
                # The last page only fills up to the limit
                'limit': min(1000, limit - (page - 1) * 1000),
                'page': page,
            }

            try:
                logger.info(f'Fetching tags from Danbooru, page {page}...')
                tags = self._get_json('/tags.json', params)
                if not isinstance(tags, list):
                    logger.warning(f'Unexpected Danbooru response on page {page}: {tags!r}')
                    continue
                yield tags
            except _Unavailable:
                return
            except Exception as e:
                logger.critical(f'Could not fetch tags: {e}')

    # ponytail: 100 names per request keeps URLs well below length limits
    CHUNK_SIZE = 100

    def get_tag_implications(self, tag_names: List[str]) -> dict:
        """
        Returns the active Danbooru tag implications for the given tags.

        Args:
            tag_names (List[str]): The antecedent tag names to look up.

        Returns:
            dict: A mapping of antecedent tag name to a list of implied tag names.
        """

        implications = {}

        for index in range(0, len(tag_names), self.CHUNK_SIZE):
            chunk = tag_names[index : index + self.CHUNK_SIZE]
            params = {
                'search[antecedent_name_comma]': ','.join(chunk),
                'search[status]': 'active',
                'limit': 1000,
            }

            try:
                results = self._get_json('/tag_implications.json', params)
                if not isinstance(results, list):
                    logger.warning(f'Unexpected Danbooru response: {results!r}')
                    continue
                for entry in results:
                    implications.setdefault(entry['antecedent_name'], []).append(entry['consequent_name'])
            except _Unavailable:
                return implications
            except Exception as e:
                logger.critical(f'Could not fetch tag implications: {e}')

        return implications

    def get_tag_categories(self, tag_names: List[str]) -> dict:
        """
        Returns the Danbooru categories of the given tags.

        Args:
            tag_names (List[str]): The tag names to look up.

        Returns:
            dict: A mapping of tag name to its numerical Danbooru category.
        """

        categories = {}

        for index in range(0, len(tag_names), self.CHUNK_SIZE):
            chunk = tag_names[index : index + self.CHUNK_SIZE]
            params = {'search[name_comma]': ','.join(chunk), 'limit': 1000}

            try:
                results = self._get_json('/tags.json', params)
                if not isinstance(results, list):
                    logger.warning(f'Unexpected Danbooru response: {results!r}')
                    continue
                for entry in results:
                    categories[entry['name']] = entry['category']
            except _Unavailable:
                return categories
            except Exception as e:
                logger.critical(f'Could not fetch tag categories: {e}')

        return categories
