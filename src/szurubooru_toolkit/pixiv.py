from pixivpy3 import AppPixivAPI as Pixiv_Module
from aiohttp.client_exceptions import ClientConnectorError
from loguru import logger

class Pixiv:
    def __init__(self, token):
        self.client = Pixiv_Module()
        self.client.auth(refresh_token=token)


    def get_result(self, result_url):
        temp = result_url.split('=')
        post_id = int(result_url.split('=')[-1])
        logger.debug(f'Getting result from id {post_id}')
        for _ in range(1, 12):
            try:
                result = self.client.illust_detail(post_id)
                logger.debug(f'Returning result: {result}')
                break
            except ClientConnectorError:
                logger.debug('Could not establish connection to Pixiv, trying again in 5s...')
                sleep(5)
            except KeyError:  # In case the post got deleted but is still indexed
                result = None
                logger.debug('Got no result')
                break
        else:
            result = None

        return result

    def get_tags(self, result):
        tags = []
        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                temp = tag['name']
                if not temp == None:
                    if not temp == "R-18":
                        tags.append(temp)
        logger.debug(f'Returning tags {tags}')
        return tags

    def get_rating(self, result):
        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                if tag['name'] == "R-18":
                    return 'unsafe'
        return 'safe'
