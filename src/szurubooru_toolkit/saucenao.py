from __future__ import annotations

from asyncio.exceptions import TimeoutError
from io import BytesIO
from time import sleep
from typing import Coroutine  # noqa TYP001

from aiohttp.client_exceptions import ContentTypeError
from loguru import logger
from pybooru.moebooru import Moebooru
from pysaucenao import SauceNao as PySauceNao
from syncer import sync

from szurubooru_toolkit import Config
from szurubooru_toolkit import Danbooru
from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit.utils import audit_rating
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import scrape_sankaku


class SauceNao:
    """Handles everything related to SauceNAO and aggregating the results."""

    def __init__(self, config: Config) -> None:
        """Initialize the SauceNAO object with Booru clients as attributes.

        Following clients will be set as attributes:

        * `self.danbooru`
        * `self.gelbooru`
        * `self.konachan`
        * `self.pysaucenao`
        * `self.yandere`

        Args:
            config (Config): Config object with user configuration from `config.toml`.
        """

        self.pysaucenao = PySauceNao(api_key=config.auto_tagger['saucenao_api_token'], min_similarity=80.0)
        if not config.auto_tagger['saucenao_api_token'] == 'None':
            logger.debug('Using SauceNAO API token')

        self.danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
        self.gelbooru = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
        self.konachan = Moebooru('konachan', config.konachan['user'], config.konachan['password'])
        self.yandere = Moebooru('yandere', config.yandere['user'], config.yandere['password'])

    @sync
    async def get_metadata(self, content_url: str, image: bytes = None) -> tuple:
        """Retrieve results from SauceNAO and aggregate all metadata.

        Args:
            content_url (str): Image URL where SauceNAO should retrieve the image from.
            image (bytes): The media file as bytes.

        Returns:
            tuple: Contains `tags`, `source`, `rating`, `limit_short` and `limit_long`.
        """

        # Set default values
        # Should not affect scraped data
        metadata = dict(tags=[], source='', rating='')
        metadata_dan = metadata.copy()
        metadata_gel = metadata.copy()
        metadata_san = metadata.copy()
        metadata_yan = metadata.copy()
        metadata_kona = metadata.copy()

        limit_short = 1
        limit_long = 10

        response = await self.get_result(content_url, image)

        # Sometimes multiple results from the same Booru are found.
        # Results are sorted by their similiarity (highest first).
        # As soon as the highest similarity result is processed, skip other results from the same booru.
        danbooru_found = False
        gelbooru_found = False
        yandere_found = False
        konachan_found = False

        if response and not response == 'Limit reached':
            for result in response:
                if result.url is not None and 'danbooru' in result.url and not danbooru_found:
                    result_dan = self.danbooru.get_result(result.danbooru_id)

                    if not result_dan:
                        continue

                    metadata_dan['tags'] = self.danbooru.get_tags(result_dan)
                    metadata_dan['rating'] = convert_rating(self.danbooru.get_rating(result_dan))
                    metadata_dan['source'] = result.url

                    danbooru_found = True
                elif result.url is not None and 'gelbooru' in result.url and not gelbooru_found:
                    result_gel = await self.gelbooru.get_result(result.url)

                    if not result_gel:
                        continue

                    metadata_gel['tags'] = self.gelbooru.get_tags(result_gel)
                    metadata_gel['rating'] = convert_rating(result_gel.rating)
                    metadata_gel['source'] = result.url

                    gelbooru_found = True
                elif result.url is not None and 'yande.re' in result.url and not yandere_found:
                    result_yan = self.yandere.post_list(tags='id:' + str(result.data['yandere_id']))[0]

                    if not result_yan:
                        continue

                    metadata_yan['tags'] = result_yan['tags'].split()
                    metadata_yan['rating'] = convert_rating(result_yan['rating'])
                    metadata_yan['source'] = result.url

                    yandere_found = True
                elif result.url is not None and 'konachan' in result.url and not konachan_found:
                    result_kona = self.konachan.post_list(tags='id:' + str(result.data['konachan_id']))[0]

                    if not result_kona:
                        continue

                    metadata_kona['tags'] = result_kona['tags'].split()
                    metadata_kona['rating'] = convert_rating(result_kona['rating'])
                    metadata_kona['source'] = result.url

                    konachan_found = True
                elif result.url is not None and 'sankaku' in result.url:
                    metadata_san['tags'], metadata_san['rating'] = scrape_sankaku(result.url)
                    metadata_san['source'] = result.url

            limit_short = response.short_remaining
            logger.debug(f'Limit short: {limit_short}')
            limit_long = response.long_remaining
            logger.debug(f'Limit long: {limit_long}')

        # Collect scraped tags
        tags = list(
            set().union(
                metadata_gel['tags'],
                metadata_san['tags'],
                metadata_dan['tags'],
                metadata_yan['tags'],
                metadata_kona['tags'],
            ),
        )

        # Collect scraped sources. Remove empty strings/sources in the process.
        source = collect_sources(
            metadata_gel['source'],
            metadata_san['source'],
            metadata_dan['source'],
            metadata_yan['source'],
            metadata_kona['source'],
        )
        source_debug = source.replace('\n', '\\n')  # Don't display line breaks in logs

        # Get highest rating
        rating = audit_rating(
            metadata_gel['rating'],
            metadata_san['rating'],
            metadata_dan['rating'],
            metadata_yan['rating'],
            metadata_kona['rating'],
        )

        if response == 'Limit reached':
            limit_long = 0

        if metadata_dan['tags']:
            logger.debug('Found result in Danbooru')
        if metadata_gel['tags']:
            logger.debug('Found result in Gelbooru')
        if metadata_san['tags']:
            logger.debug('Found result in Sankaku')
        if metadata_yan['tags']:
            logger.debug('Found result in Yande.re')
        if metadata_kona['tags']:
            logger.debug('Found result in Konachan')

        logger.debug(f'Returning tags: {tags}')
        logger.debug(f'Returning sources: {source_debug}')
        logger.debug(f'Returning rating: {rating}')

        return tags, source, rating, limit_short, limit_long

    async def get_result(self, content_url: str, image: bytes = None) -> Coroutine | None:
        """Fetch results from SauceNAO for supplied URL/image.

        If `image` is passed, upload the image from that local path to SauceNAO.
        Otherwise, let SauceNAO retrieve the result from `content_url`.

        If this SauceNAO cannot be reached, try again every five seconds for up to a minute.

        Args:
            content_url (str): Image URL where SauceNAO should retrieve the image from.
            image (bytes): The media as bytes.

        Returns:
            Coroutine | None: A coroutine with the pysaucenao search results or None in case of search errors.
        """

        for _ in range(1, 12):
            try:
                if image:
                    logger.debug('Trying to get result from uploaded file...')
                    response = await self.pysaucenao.from_file(BytesIO(image))
                else:
                    logger.debug(f'Trying to get result from content_url: {content_url}')
                    response = await self.pysaucenao.from_url(content_url)
                logger.debug(f'Received response {response}')

                break
            except (ContentTypeError, TimeoutError):
                logger.debug('Could not establish connection to SauceNAO, trying again in 5s...')
                sleep(5)
            except Exception as e:
                if 'Daily Search Limit Exceeded' in e.args[0]:
                    response = 'Limit reached'
                else:
                    if image:
                        logger.warning(f'Could not get result from SauceNAO with uploaded image "{content_url}": {e}')
                    else:
                        logger.warning(f'Could not get result from SauceNAO with image URL "{content_url}": {e}')
                    response = None
                break
        else:
            logger.warning('Could not establish connection to SauceNAO, trying with next post...')
            response = None

        return response
