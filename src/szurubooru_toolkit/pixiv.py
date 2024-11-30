from time import sleep
from typing import Any
from typing import List
from typing import Optional

from aiohttp.client_exceptions import ClientConnectorError
from loguru import logger
from pixivpy3 import AppPixivAPI as Pixiv_Module


class Pixiv:
    def __init__(self, token: str) -> None:
        """
        Initializes a Pixiv object and sets up the client.

        This method initializes a Pixiv object and sets up the client. It uses the provided token to authenticate with the
        Pixiv API.

        Args:
            token (str): The refresh token for the Pixiv API.
        """

        self.client = Pixiv_Module()
        self.client.auth(refresh_token=token)

    def get_result(self, result_url: str) -> Optional[dict]:
        """
        Retrieves a post from Pixiv by its ID.

        This method retrieves a post from Pixiv by its ID. The ID is extracted from the provided URL. It tries to fetch
        the post up to 11 times, with a 5 second delay between each attempt. If an error occurs during the request, it logs
        the error and tries again. If the post is from Pixiv Fanbox, it does not attempt to fetch it as they are paywalled.

        Args:
            result_url (str): The URL of the post to retrieve.

        Returns:
            dict: The retrieved post if it exists and is not from Pixiv Fanbox, None otherwise.

        Raises:
            ClientConnectorError: If a connection to Pixiv cannot be established.
            KeyError: If the post got deleted but is still indexed.
        """

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

    def get_tags(self, result: Any) -> List[str]:
        """
        Extracts tags from the result.

        This method extracts the tags from the result object. If the result object has an `illust` attribute and this
        attribute has a `tags` attribute, it iterates over the tags and adds them to a list. It ignores the 'R-18' tag.

        Args:
            result (Any): The result object from which to extract the tags.

        Returns:
            List[str]: The list of tags extracted from the result.
        """

        tags = []

        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                temp = tag['name']
                if temp is not None:
                    if not temp == 'R-18':
                        tags.append(temp)

        logger.debug(f'Returning tags {tags}')

        return tags

    def get_rating(self, result: Any) -> str:
        """
        Determines the rating of the result.

        This method determines the rating of the result object. If the result object has an `illust` attribute and this
        attribute has a `tags` attribute, it iterates over the tags. If it finds the 'R-18' tag, it returns 'unsafe'.
        Otherwise, it returns 'safe'.

        Args:
            result (Any): The result object from which to determine the rating.

        Returns:
            str: The rating of the result ('unsafe' or 'safe').
        """

        if result.illust and result.illust.tags:
            for tag in result.illust.tags:
                if tag['name'] == 'R-18':
                    return 'unsafe'
        return 'safe'

    @classmethod
    def extract_pixiv_artist(cls, pixiv_artist: str) -> str:
        """
        Extracts the Pixiv artist name and checks if it exists on Danbooru.

        This method extracts the Pixiv artist name and checks if it exists on Danbooru. If the artist does not exist on
        Danbooru, it sanitizes the Pixiv artist name and checks again. If the artist still does not exist, it uses the
        sanitized Pixiv artist name. If the `use_pixiv_artist` option is enabled in the configuration and the artist does
        not exist on Danbooru, it tries to create the artist on Szurubooru.

        Args:
            pixiv_artist (str): The Pixiv artist name to extract.

        Returns:
            str: The artist name if it exists on Danbooru or the sanitized Pixiv artist name otherwise.

        Raises:
            Exception: If the artist cannot be created on Szurubooru.
        """

        from szurubooru_toolkit import config
        from szurubooru_toolkit import danbooru
        from szurubooru_toolkit import szuru

        if pixiv_artist:
            artist_danbooru = danbooru.search_artist(pixiv_artist)

            artist_pixiv_sanitized = pixiv_artist.lower().replace(' ', '_')
            # Sometimes \3000 gets appended from the result for whatever reason
            artist_pixiv_sanitized = artist_pixiv_sanitized.replace('\u3000', '')

            if not artist_danbooru:
                artist_danbooru = danbooru.search_artist(artist_pixiv_sanitized)

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
