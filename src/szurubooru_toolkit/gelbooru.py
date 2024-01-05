from time import sleep

from aiohttp.client_exceptions import ClientConnectorError
from loguru import logger
from pygelbooru import Gelbooru as Gelbooru_Module


class Gelbooru:
    def __init__(self) -> None:
        """
        Initializes a Gelbooru object and sets up the client.

        Returns:
            None
        """

        self.client = Gelbooru_Module()

    async def get_result(self, result_url: str) -> dict:
        """
        Retrieves a post from Gelbooru by its ID.

        This method retrieves a post from Gelbooru by its ID. The ID is extracted from the provided URL. It tries to fetch
        the post up to 11 times, with a 5 second delay between each attempt. If an error occurs during the request, it logs
        the error and tries again.

        Args:
            result_url (str): The URL of the post to retrieve.

        Returns:
            dict: The retrieved post.

        Raises:
            ClientConnectorError: If a connection to Gelbooru cannot be established.
        """

        post_id = int(result_url.split('=')[-1])
        logger.debug(f'Getting result from id {post_id}')

        for _ in range(1, 12):
            try:
                result = await self.client.get_post(post_id)
                logger.debug(f'Returning result: {result}')
                break
            except ClientConnectorError:
                logger.debug('Could not establish connection to Gelbooru, trying again in 5s...')
                sleep(5)
            except KeyError:  # In case the post got deleted but is still indexed
                result = None
                logger.debug('Got no result')
                break
        else:
            logger.debug('Could not establish connection to Gelbooru. Skip tagging this post with Gelbooru...')
            result = None

        return result

    def get_tags(self, result):
        tags = [tag for tag in result.tags if tag]
        logger.debug(f'Returning tags {tags}')

        return tags
