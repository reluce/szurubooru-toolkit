import os
import urllib
from misc.helpers import resize_image, convert_rating, audit_rating, collect_tags, collect_sources
from classes.boorus.danbooru import Danbooru
from classes.boorus.gelbooru import Gelbooru
from classes.boorus.pixiv import Pixiv
from pysaucenao import SauceNao as PySauceNao
from classes.scraper import Scraper
from syncer import sync

class SauceNao:
    def __init__(self, user_input):
        self.local_temp_path    = user_input.local_temp_path
        self.pysaucenao         = PySauceNao(
            api_key=user_input.saucenao_api_key,
            min_similarity=80.0
            )
        self.danbooru = Danbooru(
            danbooru_user    = user_input.danbooru_user,
            danbooru_api_key = user_input.danbooru_api_key
        )
        self.gelbooru = Gelbooru(
            gelbooru_user    = user_input.danbooru_user,
            gelbooru_api_key = user_input.danbooru_api_key
        )
        # self.pixiv = Pixiv(
        #     pixiv_user    = user_input.pixiv_user,
        #     pixiv_pass    = user_input.pixiv_pass,
        #     refresh_token = user_input.pixiv_token,
        # )
        self.szuru_public       = user_input.szuru_public

    @sync
    async def get_metadata(self, post):
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
        metadata_def = dict(
            tags   = [],
            source = '',
            rating = 'safe'
        )
        metadata_dan = metadata_def.copy()
        metadata_gel = metadata_def.copy()
        metadata_san = metadata_def.copy()

        limit_short = 1
        limit_long  = 10

        results = await self.get_result(post.image_url)

        if results.results:
            for rs in results:
                try:
                    if rs.url != None and 'danbooru' in rs.url:
                        try:
                            result = self.danbooru.get_result(rs.url)

                            tags   = self.danbooru.get_tags(result)
                            rating = convert_rating(self.danbooru.get_rating(result))
                            source = rs.url

                            metadata_dan['tags']   = tags
                            metadata_dan['source'] = source
                            metadata_dan['rating'] = rating
                        except Exception as e:
                            print()
                            print(f'Failed to fetch data from Danbooru for post {post.id}: {e}')
                            print(f'URL: {rs.url}')
                    elif rs.url != None and 'gelbooru' in rs.url:
                        try:
                            result = await self.gelbooru.get_result(rs.url)

                            tags   = self.gelbooru.get_tags(result)
                            rating = convert_rating(self.gelbooru.get_rating(result))
                            source = rs.url
                            
                            metadata_gel['tags']   = tags
                            metadata_gel['source'] = source
                            metadata_gel['rating'] = rating
                        except Exception as e:
                            print()
                            print(f'Failed to fetch data from Gelbooru for post {post.id}: {e}')
                            print(f'URL: {rs.url}')
                    elif rs.url != None and 'sankaku' in rs.url:
                        t, s, r                = Scraper.scrape_sankaku(rs.url)
                        metadata_san['tags']   = t
                        metadata_san['source'] = s
                    # elif rs.url != None and 'pixiv' in rs.url:
                    #     self.pixiv.get_result(rs.url)
                    #     tags   = self.pixiv.get_tags()
                    #     source = rs.url
                    #     rating = convert_rating(self.pixiv.get_rating())
                    #     metadata_pix['tags'] = tags
                    #     metadata_pix['source'] = source
                    #     metadata_pix['rating'] = rating
                    # metadata_san['rating'] = r
                    # elif rs.index == 'E-Hentai':
                    #     t, s, r = Scraper.scrape_ehentai(rs.url)
                    #     metadata_hen['tags'] = t
                    #     metadata_hen['source'] = s
                    #     metadata_hen['rating'] = r
                except TypeError as e:
                    print()
                    print(f'Could not tag post {post.id}: {e}')

            limit_short = results.short_remaining
            limit_long  = results.long_remaining

        # Collect scraped tags
        tags = collect_tags(
            metadata_gel['tags'],
            metadata_san['tags'],
            metadata_dan['tags']
        )

        # Collect scraped sources
        source = collect_sources(
            metadata_gel['source'],
            metadata_san['source'],
            metadata_dan['source']
        )

        # Audit final rating
        rating = audit_rating(
            metadata_gel['rating'],
            metadata_san['rating'],
            metadata_dan['rating']
        )

        return tags, source, rating, limit_short, limit_long

    async def get_result(self, szuru_image_url):
        """
        If szurubooru is public, let SauceNAO fetch the image from supplied URL.
        If not not, download the image to our temporary path and upload it to SauceNAO.

        Arguments:
            szuru_image_url: image URL from the szurubooru server

        Returns:
            results: pysaucenao search results
        """
        if self.szuru_public == True:
            try:
                results = await self.pysaucenao.from_url(szuru_image_url)
            except Exception as e:
                results = None
                print(f'Could not get result from SauceNAO with image URL: {e}')
        else:
            try:
                filename = szuru_image_url.split('/')[-1]
                local_file_path = urllib.request.urlretrieve(szuru_image_url, self.local_temp_path + filename)[0]

                # Resize images larger than 3MB to reduce load on servers
                image_size = os.path.getsize(local_file_path)

                if image_size > 3000000:
                    resize_image(local_file_path)

                results = await self.pysaucenao.from_file(local_file_path)

                # Remove temporary image
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
            except Exception as e:
                results = None
                print(f'Could not get result from SauceNAO with uploaded image: {e}')

        return results
