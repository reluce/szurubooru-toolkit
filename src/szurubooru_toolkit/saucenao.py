import os
import urllib
from asyncio.exceptions import TimeoutError
from pathlib import Path
from time import sleep

from aiohttp.client_exceptions import ContentTypeError
from loguru import logger
from pybooru.moebooru import Moebooru
from pysaucenao import SauceNao as PySauceNao
from syncer import sync

from szurubooru_toolkit import Danbooru
from szurubooru_toolkit import Gelbooru
from szurubooru_toolkit.utils import audit_rating
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import resize_image
from szurubooru_toolkit.utils import scrape_sankaku


class SauceNao:
    def __init__(self, config):
        self.pysaucenao = PySauceNao(api_key=config.auto_tagger['saucenao_api_token'], min_similarity=80.0)
        if not config.auto_tagger['saucenao_api_token'] == 'None':
            logger.debug('Using SauceNAO API token')

        self.danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
        self.gelbooru = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])
        self.yandere = Moebooru('yandere', config.yandere['user'], config.yandere['password'])
        self.konachan = Moebooru('konachan', config.konachan['user'], config.konachan['password'])

    @sync
    async def get_metadata(self, post_url: str, szuru_public: bool, tmp_path: str, tmp_media_path: str = None):
        """
        Scrape and collect tags, sources, and ratings from popular imageboards
        Simply put, it's a wrapper for get_result() and scrape_<image_board>()

        Arguments:
            szuru_image_url: image URL from the local Szurubooru server

        Returns:
            tags: self descriptive
            source: URL of the image source
            rating: either 'unsafe', 'safe' or 'sketchy'
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

        response = await self.get_result(post_url, szuru_public, tmp_path, tmp_media_path)

        # Sometimes multiple results from the same Booru are found.
        # Results are sorted by their similiarity (highest first).
        # As soon as the highest similarity result is processed, skip other results from the same booru.
        danbooru_found = False
        gelbooru_found = False
        yandere_found = False
        konachan_found = False

        if response:
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
                    metadata_san['tags'], metadata_san['source'], metadata_san['rating'] = scrape_sankaku(result.url)

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

    async def get_result(self, post_url: str, szuru_public: bool, tmp_path: str, tmp_media_path: str = None):
        """
        If szurubooru is public, let SauceNAO fetch the image from supplied URL.
        If not not, download the image to our temporary path and upload it to SauceNAO.

        Arguments:
            post_url: image URL from the szurubooru server

        Returns:
            results: pysaucenao search results
        """

        if szuru_public:
            for _ in range(1, 12):
                try:
                    logger.debug(f'Trying to get result from post_url: {post_url}')
                    response = await self.pysaucenao.from_url(post_url)
                except (ContentTypeError, TimeoutError):
                    logger.warning('Could not establish connection to SauceNAO, trying again in 5s...')
                    sleep(5)
                except Exception as e:
                    response = None
                    logger.warning(f'Could not get result from SauceNAO with image URL "{post_url}": {e}')
                    break
        else:
            for _ in range(1, 12):
                try:
                    if not tmp_media_path:
                        filename = post_url.split('/')[-1]
                        tmp_file = urllib.request.urlretrieve(post_url, Path(tmp_path) / filename)[0]
                    else:
                        tmp_file = tmp_media_path

                    logger.debug(f'Trying to get result from tmp_file: {tmp_file}')

                    # Resize images larger than 2MB to reduce load on servers
                    image_size = os.path.getsize(tmp_file)

                    if image_size > 2000000:
                        resize_image(tmp_file)

                    response = await self.pysaucenao.from_file(tmp_file)
                    logger.debug(f'Received response {response}')

                    # Remove temporary image if the script was not called from upload-media
                    if not tmp_media_path:
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)

                    break
                except (ContentTypeError, TimeoutError):
                    logger.warning('Could not establish connection to SauceNAO, trying again in 5s...')
                    sleep(5)
                except Exception as e:
                    if 'Daily Search Limit Exceeded' in e.args[0]:
                        response = 'Limit reached'
                    else:
                        logger.warning(f'Could not get result from SauceNAO with uploaded image "{post_url}": {e}')
                        response = None
                    break
            else:
                logger.warning('Could not establish connection to SauceNAO, trying with next post...')
                response = None

        return response
