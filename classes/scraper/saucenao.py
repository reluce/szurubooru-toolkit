import os
import urllib
from misc.helpers import resize_image, convert_rating, audit_rating, collect_tags, collect_sources, check_similarity
from pysaucenao import SauceNao as PySauceNao
from classes.scraper import Scraper
from syncer import sync

class SauceNao:
    def __init__(self, *, local_temp_path, api_key):
        self.local_temp_path    = local_temp_path
        self.similarity_cutline = 80

        self.pysaucenao        = PySauceNao(api_key=api_key)

    @sync
    async def get_metadata(self, szuru_image_url):
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

        # set default values
        # should not affect scraped data
        metadata_def = dict(
            tags   = [],
            source = '',
            rating = 'safe'
        )
        metadata_gel = metadata_def.copy()
        metadata_san = metadata_def.copy()
        metadata_dan = metadata_def.copy()

        results = await self.get_result(szuru_image_url)
        results_similar = list(filter(lambda x: check_similarity(x, self.similarity_cutline), results))

        for rs in results_similar:
            if rs.index == 'Gelbooru':
                t, s, r = Scraper.scrape_gelbooru(rs.url)
                metadata_gel['tags'] = t
                metadata_gel['source'] = s
                metadata_gel['rating'] = r
            elif rs.index == 'Sankaku Channel':
                t, s, r = Scraper.scrape_sankaku(rs.url)
                metadata_san['tags'] = t
                metadata_san['source'] = s
                metadata_san['rating'] = r
            elif rs.index == 'Danbooru':
                t, s, r = Scraper.scrape_danbooru(rs.url)
                metadata_dan['tags'] = t
                metadata_dan['source'] = s
                metadata_dan['rating'] = r
            # elif rs.index == 'Pixiv':
            #     t, s, r = Scraper.scrape_pixiv(rs.url)
            #     metadata_pix['tags'] = t
            #     metadata_pix['source'] = s
            #     metadata_pix['rating'] = r
            # elif rs.index == 'E-Hentai':
            #     t, s, r = Scraper.scrape_ehentai(rs.url)
            #     metadata_hen['tags'] = t
            #     metadata_hen['source'] = s
            #     metadata_hen['rating'] = r

        # collect scraped tags
        tags = collect_tags(
            metadata_gel['tags'],
            metadata_san['tags'],
            metadata_dan['tags']
        )

        # collect scraped sources
        source = collect_sources(
            metadata_gel['source'],
            metadata_san['source'],
            metadata_dan['source']
        )

        # audit final rating
        rating = audit_rating(
            metadata_gel['rating'],
            metadata_san['rating'],
            metadata_dan['rating']
        )

        return tags, source, rating

    async def get_result(self, szuru_image_url):
        """
        Get search results from SauceNao with given image URL

        Arguments:
            szuru_image_url: image URL from the local Szurubooru server

        Returns:
            results: pysaucenao search results
        """
        try:
            results = await self.pysaucenao.from_url(szuru_image_url)
        except:
            filename = szuru_image_url.split('/')[-1]
            local_file_path = urllib.request.urlretrieve(szuru_image_url, self.local_temp_path + filename)[0]

            # Resize image if it's too big. IQDB limit is 8192KB or 7500x7500px.
            # Resize images bigger than 3MB to reduce stress on iqdb.
            image_size = os.path.getsize(local_file_path)

            if image_size > 3000000:
                resize_image(local_file_path)

            results = await self.pysaucenao.from_file(local_file_path)

            # Remove temporary image
            if os.path.exists(local_file_path):
                os.remove(local_file_path)

        return results
