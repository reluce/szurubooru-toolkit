import os
import urllib

from szuru_toolkit import Danbooru
from szuru_toolkit import Gelbooru
from szuru_toolkit import scrape_sankaku
from szuru_toolkit.utils import audit_rating
from szuru_toolkit.utils import convert_rating
from szuru_toolkit.utils import resize_image

from pysaucenao import SauceNao as PySauceNao
from syncer import sync


class SauceNao:
    def __init__(self, config):
        self.pysaucenao = PySauceNao(api_key=config.auto_tagger['saucenao_api_token'], min_similarity=80.0)
        self.danbooru = Danbooru(config.danbooru['user'], config.danbooru['api_key'])
        self.gelbooru = Gelbooru(config.gelbooru['user'], config.gelbooru['api_key'])

    @sync
    async def get_metadata(self, post_url: str, szuru_public: bool, tmp_path):
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

        limit_short = 1
        limit_long = 10

        response = await self.get_result(post_url, szuru_public, tmp_path)

        if response.results:
            for result in response:
                if result.url is not None and 'danbooru' in result.url:
                    result_dan = self.danbooru.get_result(result.url)

                    metadata_dan['tags'] = self.danbooru.get_tags(result_dan)
                    metadata_dan['rating'] = convert_rating(self.danbooru.get_rating(result_dan))
                    metadata_dan['source'] = result.url
                elif result.url is not None and 'gelbooru' in result.url:
                    result_gel = await self.gelbooru.get_result(result.url)

                    metadata_gel['tags'] = await self.gelbooru.get_tags(result_gel)
                    metadata_gel['rating'] = convert_rating(self.gelbooru.get_rating(result_gel))
                    metadata_gel['source'] = result.url
                elif result.url is not None and 'sankaku' in result.url:
                    metadata_san['tags'], metadata_san['source'], metadata_san['rating'] = scrape_sankaku(result.url)

            limit_short = response.short_remaining
            limit_long = response.long_remaining

        # Collect scraped tags
        tags = list(set().union(metadata_gel['tags'], metadata_san['tags'], metadata_dan['tags']))

        # Collect scraped sources
        source = [metadata_gel['source'], metadata_san['source'], metadata_dan['source']]

        # Audit final rating
        rating = audit_rating(metadata_gel['rating'], metadata_san['rating'], metadata_dan['rating'])

        return tags, source, rating, limit_short, limit_long

    async def get_result(self, post_url: str, szuru_public: bool, tmp_path: str):
        """
        If szurubooru is public, let SauceNAO fetch the image from supplied URL.
        If not not, download the image to our temporary path and upload it to SauceNAO.

        Arguments:
            post_url: image URL from the szurubooru server

        Returns:
            results: pysaucenao search results
        """
        if szuru_public:
            try:
                results = await self.pysaucenao.from_url(post_url)
            except Exception as e:
                results = None
                print(f'Could not get result from SauceNAO with image URL: {e}')
        else:
            try:
                filename = post_url.split('/')[-1]
                tmp_file = urllib.request.urlretrieve(post_url, tmp_path + filename)[0]

                # Resize images larger than 2MB to reduce load on servers
                image_size = os.path.getsize(tmp_file)

                if image_size > 2000000:
                    resize_image(tmp_file)

                results = await self.pysaucenao.from_file(tmp_file)

                # Remove temporary image
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception as e:
                results = None
                print(f'Could not get result from SauceNAO with uploaded image: {e}')

        return results
