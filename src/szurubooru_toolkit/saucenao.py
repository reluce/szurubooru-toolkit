from __future__ import annotations

import re
from asyncio import sleep
from asyncio.exceptions import TimeoutError
from io import BytesIO
from typing import Any
from typing import Coroutine  # noqa TYP001

import tldextract
from aiohttp.client_exceptions import ContentTypeError
from loguru import logger
from pysaucenao import SauceNao as PySauceNao

from szurubooru_toolkit import Config


class SauceNao:
    """Handles everything related to SauceNAO and aggregating the results."""

    def __init__(self, config: Config) -> None:
        """Initialize the SauceNAO object."""
        self.pysaucenao = PySauceNao(api_key=config.auto_tagger['saucenao_api_token'], min_similarity=80.0)
        if not config.auto_tagger['saucenao_api_token'] == 'None':
            logger.debug('Using SauceNAO API token')

        self.retry_attempts = 12
        self.retry_delay = 5

    def get_base_domain(self, url: str) -> str:
        extracted = tldextract.extract(url)
        return extracted.domain

    async def get_metadata(
        self,
        content_url: str,
        image: bytes | None = None,
    ) -> tuple[dict[str, dict[str, int | None] | Any], int, int]:
        """Retrieve results from SauceNAO and aggregate all metadata.

        This function extracts image metadata from multiple sources such as pixiv, Danbooru, Gelbooru, Yandere,
        Konachan and Sankaku, using the SauceNAO reverse image search tool. The metadata is then collected and
        returned in a tuple format. The function also takes care of request limit issues, informing about the
        remaining short and long limit.

        Parameters
        ----------
        content_url : str
            The URL of the szurubooru content from where metadata needs to be extracted.
            SauceNAO needs to be able to reach this URL.
        image : Optional[bytes], optional
            The image data in bytes format, if available. Defaults to None.

        Returns
        -------
        Tuple[Dict[str, Dict[str, int | None] | Any], int, int]
            A tuple containing a dictionary of metadata, short limit remaining, and long limit remaining.
            The metadata dictionary keys are domain names and the values are either another dictionary containing
            the common booru name and post_id or the result object (only with pixiv).
            The dictionary values for 'site' are source-specific strings
            and for 'post_id' are integers representing the post id from the source site.

        Raises
        ------
        Exception
            Any exceptions raised while extracting metadata or due to request limits being reached are propagated
            upwards.
        """

        response = await self.get_result(content_url, image)

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
                                matches[site] = (
                                    {'site': site_keys[site], 'post_id': int(post_id[0])} if post_id else None
                                )
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
            response.long_remaining = 0

        return matches, short_remaining, long_remaining

    async def get_result(self, content_url: str, image: bytes = None) -> Coroutine | None:
        for attempt in range(self.retry_attempts):
            try:
                if image:
                    logger.debug('Trying to get result from uploaded file...')
                    response = await self.pysaucenao.from_file(BytesIO(image))
                else:
                    logger.debug(f'Trying to get result from content_url: {content_url}')
                    response = await self.pysaucenao.from_url(content_url)

                logger.debug(f'Received response {response}')
                return response

            except (ContentTypeError, TimeoutError):
                logger.debug('Could not establish connection to SauceNAO, trying again in 5s...')
                if attempt < self.retry_attempts - 1:  # no need to sleep on the last attempt
                    await sleep(self.retry_delay)

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
