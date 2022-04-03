import pybooru
from loguru import logger
from pybooru import Danbooru as Danbooru_Module


class Danbooru:
    def __init__(self, danbooru_user, danbooru_api_key):
        if not danbooru_user == 'None' and not danbooru_api_key == 'None':
            self.client = Danbooru_Module('danbooru', username=danbooru_user, api_key=danbooru_api_key)
            logger.debug(f'Using Danbooru user {danbooru_user} with API key')
        else:
            self.client = Danbooru_Module('danbooru')
            logger.debug('Using Danbooru without user and API key')

    def get_by_md5(self, md5sum):
        try:
            logger.debug(f'Trying to fetch result by md5sum {md5sum}')
            self.result = self.client.post_list(md5=md5sum)
            self.source = self.result['source']
            logger.debug(f'Returning result: {self.result}')
        except pybooru.exceptions.PybooruHTTPError:
            logger.debug('Got no result')
            self.result = None

        return self.result

    def get_result(self, post_id):
        result = self.client.post_show(post_id)
        logger.debug(f'Returning result: {result}')

        return result

    def get_tags(self, result):
        result = result['tag_string'].split()
        logger.debug(f'Returning tags: {result}')

        return result

    def get_rating(self, result):
        result_rating = result['rating']
        logger.debug(f'Returning rating: {result_rating}')

        return result_rating
