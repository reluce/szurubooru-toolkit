from __future__ import annotations

import re
import threading
import time
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from szurubooru_toolkit.config import Config


SEARCH_URL = 'https://saucenao.com/search.php'

# Domains the toolkit knows how to handle, as matched by get_base_domain()
KNOWN_DOMAINS = ('pixiv', 'donmai', 'gelbooru', 'yande', 'konachan', 'sankakucomplex')


class SauceNaoResult:
    """A single SauceNAO match with the fields the toolkit consumes."""

    def __init__(self, result_json: dict) -> None:
        header = result_json.get('header', {})
        data = result_json.get('data', {})

        self.similarity = float(header.get('similarity', 0))
        self.index_id = header.get('index_id')
        self.urls = list(data.get('ext_urls', []))
        self.author_name = data.get('member_name') or data.get('author_name')

        # For pixiv results, expose the canonical illust_id URL since downstream
        # code extracts the post ID from the 'illust_id=' query param.
        if data.get('pixiv_id'):
            self.url = f'https://www.pixiv.net/member_illust.php?mode=medium&illust_id={data["pixiv_id"]}'
            if self.url not in self.urls:
                self.urls.insert(0, self.url)
        else:
            self.url = self.urls[0] if self.urls else None


class SauceNaoResponse:
    """A SauceNAO API response: iterable results plus the rate limit counters."""

    def __init__(self, response_json: dict, min_similarity: float) -> None:
        header = response_json.get('header', {})

        self.short_remaining = int(header.get('short_remaining', 1))
        self.long_remaining = int(header.get('long_remaining', 1))
        self.results = [
            SauceNaoResult(result)
            for result in response_json.get('results') or []
            if float(result.get('header', {}).get('similarity', 0)) >= min_similarity
        ]

    def __iter__(self):
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)


class SauceNaoCooldown:
    """Shared cooldown gate for SauceNAO's short rate limit.

    When one worker exhausts the 30-second window, it triggers the cooldown and
    every worker waits before its next SauceNAO request — instead of each worker
    sleeping (or erroring) on its own. Other pipeline steps keep running.
    """

    def __init__(self) -> None:
        self._resume_at = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Blocks until the cooldown (if any) has passed."""

        while True:
            with self._lock:
                remaining = self._resume_at - time.monotonic()

            if remaining <= 0:
                return

            time.sleep(min(remaining, 1))

    def trigger(self, seconds: float = 35.0) -> None:
        """Starts a cooldown so that all workers pause SauceNAO requests."""

        with self._lock:
            self._resume_at = max(self._resume_at, time.monotonic() + seconds)


class SauceNao:
    """Handles everything related to SauceNAO and aggregating the results."""

    def __init__(self, config: Config, transport: httpx.BaseTransport = None) -> None:
        """
        Initialize the SauceNAO client.

        Args:
            config (Config): The configuration object containing the SauceNAO API token and other settings.
            transport (httpx.BaseTransport, optional): Custom transport, used for testing.
        """

        api_token = config.auto_tagger['saucenao_api_token']
        self.api_key = api_token if api_token and api_token != 'None' else None
        if self.api_key:
            logger.debug('Using SauceNAO API token')

        self.min_similarity = 80.0
        self.results_limit = 6
        self.retry_attempts = 12
        self.retry_delay = 5
        # Pooled client shared by all tagging workers; keeps the TLS connection
        # to saucenao.com alive across requests. httpx.Client is thread-safe.
        self.client = httpx.Client(timeout=30, transport=transport)

    @staticmethod
    def get_base_domain(url: str) -> str:
        """
        Extracts the base domain from a URL.

        Returns the known domain key (e.g. 'donmai' for danbooru.donmai.us) if the host
        matches one of the sites the toolkit handles, otherwise the second-level label
        of the host.

        Args:
            url (str): The URL from which to extract the base domain.

        Returns:
            str: The base domain extracted from the URL.
        """

        host = urllib.parse.urlsplit(url).netloc.lower()
        labels = host.split('.')

        for domain in KNOWN_DOMAINS:
            if domain in labels:
                return domain

        return labels[-2] if len(labels) >= 2 else host

    def get_metadata(
        self,
        content_url: str,
        image: bytes | None = None,
    ) -> tuple[dict[str, dict[str, int | None] | Any], int, int]:
        """
        Retrieve results from SauceNAO and aggregate all metadata.

        This function extracts image metadata from multiple sources such as pixiv, Danbooru, Gelbooru, Yandere,
        Konachan and Sankaku, using the SauceNAO reverse image search tool. The metadata is then collected and
        returned in a tuple format. The function also takes care of request limit issues, informing about the
        remaining short and long limit.

        Args:
            content_url (str): The URL of the szurubooru content from where metadata needs to be extracted.
                SauceNAO needs to be able to reach this URL.
            image (Optional[bytes], optional): The image data in bytes format, if available. Defaults to None.

        Returns:
            Tuple[Dict, int, int]: A tuple containing a dictionary of metadata, short limit remaining, and long
                limit remaining. The metadata dictionary keys are domain names and the values are either another
                dictionary containing the common booru name and post_id or the result object (only with pixiv).
        """

        response = self.get_result(content_url, image)

        matches = {
            'donmai': None,
            'gelbooru': None,
            'yande': None,
            'konachan': None,
            'sankakucomplex': None,
            'pixiv': None,
        }

        if response and response != 'Limit reached':
            site_keys = {
                'pixiv': 'pixiv',
                'donmai': 'danbooru',
                'gelbooru': 'gelbooru',
                'yande': 'yandere',
                'konachan': 'konachan',
                'sankakucomplex': 'sankaku',
            }

            for result in response:
                if result.urls:
                    for url in result.urls:
                        site = self.get_base_domain(url)
                        post_id = re.findall(r'\b\d+\b', url)
                        if site in matches and not matches[site]:
                            logger.debug(f'Found result on {site.capitalize()}')
                            if site == 'pixiv':
                                matches[site] = result
                            elif site in site_keys:
                                matches[site] = {'site': site_keys[site], 'post_id': int(post_id[0])} if post_id else None
                            else:
                                continue

            logger.debug(f'Limit short: {response.short_remaining}')
            logger.debug(f'Limit long: {response.long_remaining}')

        # Even if response evaluates to False, it can still contain the limits
        try:
            short_remaining = response.short_remaining
            long_remaining = response.long_remaining
        except AttributeError:
            short_remaining = 1
            long_remaining = 1

        if response == 'Limit reached':
            long_remaining = 0

        return matches, short_remaining, long_remaining

    def get_result(self, content_url: str, image: bytes | None = None) -> SauceNaoResponse | str | None:
        """
        Attempts to get a result from SauceNAO.

        This method attempts to get a result from SauceNAO by either uploading an image or using a URL. It tries to get a
        result up to a specified number of retry attempts. If an error occurs during the request, it logs the error and
        tries again. If the daily search limit is exceeded, it returns 'Limit reached'. If it cannot establish a connection
        to SauceNAO after all attempts, it logs that it is trying with the next post and returns None.

        Args:
            content_url (str): The URL of the content to retrieve.
            image (Optional[bytes], optional): The image data in bytes format, if available. Defaults to None.

        Returns:
            SauceNaoResponse | str | None: The response from SauceNAO if it exists, 'Limit reached' if the daily
            search limit is exceeded, None otherwise.
        """

        params = {'output_type': 2, 'db': 999, 'numres': self.results_limit}
        if self.api_key:
            params['api_key'] = self.api_key

        for attempt in range(self.retry_attempts):
            try:
                if image:
                    logger.debug('Trying to get result from uploaded file...')
                    response = self.client.post(SEARCH_URL, params=params, files={'file': ('image', image)})
                else:
                    logger.debug(f'Trying to get result from content_url: {content_url}')
                    response = self.client.post(SEARCH_URL, params=params | {'url': content_url})

                response_json = response.json()
                header = response_json.get('header', {})
                message = str(header.get('message', ''))

                if 'Daily Search Limit Exceeded' in message or int(header.get('long_remaining', 1)) < 0:
                    return 'Limit reached'

                # Short limit exhausted: SauceNAO answers with 429 until the 30s window resets
                if response.status_code == 429:
                    logger.debug('SauceNAO rate limit hit, trying again in 5s...')
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay)
                    continue

                if int(header.get('status', 0)) != 0:
                    logger.warning(f'Could not get result from SauceNAO for "{content_url}": {message}')
                    return None

                result = SauceNaoResponse(response_json, self.min_similarity)
                logger.debug(f'Received response with {len(result)} results above similarity threshold')
                return result

            except (httpx.HTTPError, ValueError, TimeoutError):
                logger.debug('Could not establish connection to SauceNAO, trying again in 5s...')
                if attempt < self.retry_attempts - 1:  # no need to sleep on the last attempt
                    time.sleep(self.retry_delay)

            except Exception as e:
                if 'Daily Search Limit Exceeded' in str(e):
                    return 'Limit reached'
                else:
                    if image:
                        logger.warning(f'Could not get result from SauceNAO with uploaded image "{content_url}": {e}')
                    else:
                        logger.warning(f'Could not get result from SauceNAO with image URL "{content_url}": {e}')
                    return None

        logger.debug('Could not establish connection to SauceNAO, trying with next post...')
        return None
