from time import sleep
from typing import List
from typing import Optional

import requests
from loguru import logger
from pybooru import Danbooru as Danbooru_Module
from pybooru.exceptions import PybooruAPIError
from pybooru.exceptions import PybooruError
from pybooru.exceptions import PybooruHTTPError


class Danbooru:
    def __init__(self) -> None:
        """
        Initialize a Danbooru and a requests session client.

        Returns:
            None
        """

        self.client = Danbooru_Module('danbooru')

        self.session = requests.Session()
        headers = {'User-Agent': 'Danbooru dummy agent'}
        self.session.headers.update(headers)

    def get_by_md5(self, md5sum: str) -> Optional[dict]:
        """
        Retrieve a post from Danbooru by its MD5 hash.

        This method retrieves a post from Danbooru by its MD5 hash. It tries to fetch the post up to 11 times, with a 5
        second delay between each attempt. If the post is not found, it returns None. If an error occurs during the request,
        it logs the error and tries again. If it fails to establish a connection after 11 attempts, it logs the failure and
        returns None.

        Args:
            md5sum (str): The MD5 hash of the post to retrieve.

        Returns:
            Optional[dict]: The post as a dictionary if found, None otherwise.

        Raises:
            PybooruHTTPError: If a HTTP error occurs during the request.
            PybooruError: If a general error occurs during the request.
            PybooruAPIError: If an API error occurs during the request.
        """

        for _ in range(1, 12):
            try:
                logger.debug(f'Trying to fetch result by md5sum {md5sum}')
                result = self.client.post_list(md5=md5sum)
                logger.debug(f'Returning result: {result}')

                break
            except PybooruHTTPError as e:
                if 'Not Found' in e._msg:
                    result = None
                    break
            except (TimeoutError, PybooruError, PybooruHTTPError, PybooruAPIError):
                logger.debug('Got no result')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru, returning None...')
            result = None

        return result

    def get_result(self, post_id: int) -> Optional[dict]:
        """
        Retrieve a post from Danbooru by its post ID.

        This method retrieves a post from Danbooru by its post ID. It tries to fetch the post up to 11 times, with a 5
        second delay between each attempt. If the post is not found, it returns None. If an error occurs during the request,
        it logs the error and tries again. If it fails to establish a connection after 11 attempts, it logs the failure and
        returns None.

        Args:
            post_id (int): The ID of the post to retrieve.

        Returns:
            Optional[dict]: The post as a dictionary if found, None otherwise.

        Raises:
            PybooruHTTPError: If a HTTP error occurs during the request.
            PybooruError: If a general error occurs during the request.
            PybooruAPIError: If an API error occurs during the request.
        """

        for _ in range(1, 12):
            try:
                result = self.client.post_show(post_id)
                logger.debug(f'Returning result: {result}')

                break
            except (TimeoutError, PybooruError, PybooruHTTPError, PybooruAPIError):
                logger.debug('Could not establish connection to Danbooru, trying again in 5s...')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru. Skip tagging this post with Danbooru...')
            result = None

        return result

    def get_other_names_tag(self, other_tag: str) -> str:
        """
        Search for the main tag name of the given tag.

        This method searches for the main tag name of the supplied tag on Danbooru. It tries to fetch the tag up to 11 times,
        with a 5 second delay between each attempt. If the tag is not found, it returns None. If an error occurs during the
        request, it logs the error and tries again. If it fails to establish a connection after 11 attempts, it logs the
        failure and returns None.

        Args:
            other_tag (str): The tag you want to search for.

        Returns:
            str: The main tag if found, None otherwise.

        Raises:
            PybooruHTTPError: If a HTTP error occurs during the request.
            PybooruError: If a general error occurs during the request.
            PybooruAPIError: If an API error occurs during the request.
        """

        for _ in range(1, 12):
            try:
                search_url = f'https://danbooru.donmai.us/wiki_pages.json?search[other_names_match]={other_tag}&only=title'

                tag = self.session.get(search_url).json()[0]['title']
                self.session.close()

                logger.debug(f'Returning found tag for {other_tag}: {tag}')

                break
            except (IndexError, KeyError):
                logger.debug(f'Could not find tag for other_tag "{other_tag}"')
                tag = None

                break
            except (TimeoutError, PybooruError, PybooruHTTPError, PybooruAPIError):
                logger.debug('Could not establish connection to Danbooru, trying again in 5s...')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru. Skip search for other tag...')
            tag = None

        return tag

    def get_tags(self, result: dict) -> List[str]:
        """
        Extracts tags from the result.

        This method extracts the tags from the result dictionary and returns them as a list of strings.

        Args:
            result (dict): The result dictionary from which to extract the tags.

        Returns:
            List[str]: The list of tags extracted from the result.
        """

        result = result['tag_string'].split()
        logger.debug(f'Returning tags: {result}')

        return result

    def get_rating(self, result: dict) -> str:
        """
        Extracts the rating from the result.

        This method extracts the rating from the result dictionary and returns it as a string.

        Args:
            result (dict): The result dictionary from which to extract the rating.

        Returns:
            str: The rating extracted from the result.
        """

        result_rating = result['rating']
        logger.debug(f'Returning rating: {result_rating}')

        return result_rating

    def search_artist(self, artist: str) -> str:
        """
        Search for the main artist name on Danbooru and return it.

        This method searches for the main artist name on Danbooru. It tries to fetch the artist up to 11 times, with a 5
        second delay between each attempt. If the artist is not found, it returns None. If an error occurs during the
        request, it logs the error and tries again. If it fails to establish a connection after 11 attempts, it logs the
        failure and returns None.

        Args:
            artist (str): The artist name. Can be an alias as well.

        Returns:
            str: The main artist name if found, None otherwise.

        Raises:
            IndexError: If the artist is not found in the response.
            KeyError: If the 'name' key is not found in the response.
        """

        for _ in range(1, 12):
            try:
                result = self.client.artist_list(artist.lower())
                if result:
                    artist = result[0]['name']
                else:
                    search_url = (
                        f'https://danbooru.donmai.us/artists.json?search[any_other_name_like]={artist.lower()}&search[is_deleted]=false'
                    )
                    artist = self.session.get(search_url).json()[0]['name']
                    self.session.close()

                logger.debug(f'Returning artist: {artist}')

                break
            except (IndexError, KeyError):
                logger.debug(f'Could not find artist "{artist.lower()}"')
                artist = None

                break
            except requests.exceptions.JSONDecodeError:
                logger.debug(f'Could not load JSON for artist {artist}')
                artist = None

                break
            except (TimeoutError, PybooruError, PybooruHTTPError, PybooruAPIError):
                logger.debug('Could not establish connection to Danbooru, trying again in 5s...')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru. Skip this artist...')
            artist = None

        return artist

    def download_tags(self, query: str = '*', min_post_count: int = 10, limit: int = 100) -> List[dict]:
        """
        Download and return tags from Danbooru.

        This method downloads tags from Danbooru. It builds a URL with the provided query, minimum post count, and limit,
        and fetches the tags from that URL. It tries to fetch the tags up to the number of pages calculated from the limit,
        with a 5 second delay between each attempt. If an error occurs during the request, it logs the error and tries again.

        Args:
            query (str, optional): Search for specific tag, accepts wildcard (*). If not specified, download all tags.
                                Defaults to '*'.
            min_post_count (int, optional): The minimum amount of posts the tag should have been used in. Defaults to 10.
            limit (int, optional): The amount of tags that should be downloaded. Start from the most recent ones.
                                Defaults to 100.

        Returns:
            List[dict]: A list with found tags.

        Raises:
            PybooruHTTPError: If a HTTP error occurs during the request.
            PybooruError: If a general error occurs during the request.
            PybooruAPIError: If an API error occurs during the request.
        """

        tag_base_url = 'https://danbooru.donmai.us/tags.json'

        if limit > 1000:
            pages = limit // 1000
        else:
            pages = 1

        for page in range(1, pages + 1):
            tag_url = (
                tag_base_url
                + '?search[post_count]=>'
                + str(min_post_count)
                + '&search[name_matches]='
                + query
                + '&limit='
                + str(limit)
                + '&page='
                + str(page)
            )

            try:
                logger.info(f'Fetching tags from URL {tag_url}...')
                yield self.session.get(tag_url, timeout=30).json()
            except Exception as e:
                logger.critical(f'Could not fetch tags: {e}')

        self.session.close()
