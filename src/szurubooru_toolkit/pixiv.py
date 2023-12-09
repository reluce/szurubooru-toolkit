from time import sleep

from aiohttp.client_exceptions import ClientConnectorError
from loguru import logger
from pixivpy3 import AppPixivAPI as Pixiv_Module


class Pixiv:
    def __init__(self, token):
        self.client = Pixiv_Module()
        self.client.auth(refresh_token=token)

    def get_result(self, result_url):
        if 'pixiv.net/fanbox' not in result_url:
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
        else:
            # Don't lookup tags for Fanbox as they're paywalled
            result = None

        return result

    def get_tags(self, result):
        tags = []

        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                temp = tag['name']
                if temp is not None:
                    if not temp == 'R-18':
                        tags.append(temp)

        logger.debug(f'Returning tags {tags}')

        return tags

    def get_rating(self, result):
        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                if tag['name'] == 'R-18':
                    return 'unsafe'
        return 'safe'

    @classmethod
    def extract_pixiv_artist(cls, pixiv_artist: str) -> str:
        from szurubooru_toolkit import config
        from szurubooru_toolkit import danbooru_client
        from szurubooru_toolkit import szuru

        if pixiv_artist:
            artist_danbooru = danbooru_client.search_artist(pixiv_artist)

            artist_pixiv_sanitized = pixiv_artist.lower().replace(' ', '_')
            # Sometimes \3000 gets appended from the result for whatever reason
            artist_pixiv_sanitized = artist_pixiv_sanitized.replace('\u3000', '')

            if not artist_danbooru:
                artist_danbooru = danbooru_client.search_artist(artist_pixiv_sanitized)

            if artist_danbooru:
                artist = artist_danbooru
            else:
                artist = artist_pixiv_sanitized

            if not artist_danbooru and config.auto_tagger['use_pixiv_artist']:
                try:
                    szuru.create_tag(artist, category='artist', overwrite=True)
                except Exception as e:
                    logger.debug(f'Could not create pixiv artist {pixiv_artist}: {e}')
        else:
            artist = None

        return artist
