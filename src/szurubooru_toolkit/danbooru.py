from time import sleep
from typing import List
from typing import Optional

import httpx
from loguru import logger


class Danbooru:
    """Handles the Danbooru API calls the toolkit needs (artists, wiki pages, tag export)."""

    def __init__(self, transport: httpx.BaseTransport = None) -> None:
        """
        Initialize the Danbooru client with a pooled httpx session.

        Args:
            transport (httpx.BaseTransport, optional): Custom transport, used for testing.
        """

        self.client = httpx.Client(
            base_url='https://danbooru.donmai.us',
            headers={'User-Agent': 'Danbooru dummy agent'},
            timeout=30,
            transport=transport,
        )

    def get_other_names_tag(self, other_tag: str) -> Optional[str]:
        """
        Search for the main tag name of the given tag.

        This method searches for the main tag name of the supplied tag on Danbooru via its wiki pages. It retries on
        connection errors up to 11 times with a 5 second delay. If the tag is not found, it returns None.

        Args:
            other_tag (str): The tag you want to search for.

        Returns:
            Optional[str]: The main tag if found, None otherwise.
        """

        for _ in range(1, 12):
            try:
                params = {'search[other_names_match]': other_tag, 'only': 'title'}
                tag = self.client.get('/wiki_pages.json', params=params).json()[0]['title']

                logger.debug(f'Returning found tag for {other_tag}: {tag}')

                break
            except (IndexError, KeyError, ValueError):
                logger.debug(f'Could not find tag for other_tag "{other_tag}"')
                tag = None

                break
            except (TimeoutError, httpx.HTTPError):
                logger.debug('Could not establish connection to Danbooru, trying again in 5s...')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru. Skip search for other tag...')
            tag = None

        return tag

    def search_artist(self, artist: str) -> Optional[str]:
        """
        Search for the main artist name on Danbooru and return it.

        This method searches for the main artist name on Danbooru, first by base name, then by other names. It retries
        on connection errors up to 11 times with a 5 second delay. If the artist is not found, it returns None.

        Args:
            artist (str): The artist name. Can be an alias as well.

        Returns:
            Optional[str]: The main artist name if found, None otherwise.
        """

        for _ in range(1, 12):
            try:
                response = self.client.get('/artists.json', params={'search[name]': artist.lower()})
                response.raise_for_status()
                result = response.json()

                if result:
                    artist = result[0]['name']
                else:
                    params = {'search[any_other_name_like]': artist.lower(), 'search[is_deleted]': 'false'}
                    artist = self.client.get('/artists.json', params=params).json()[0]['name']

                logger.debug(f'Returning artist: {artist}')

                break
            except (IndexError, KeyError):
                logger.debug(f'Could not find artist "{artist.lower()}"')
                artist = None

                break
            except ValueError:
                logger.debug(f'Could not load JSON for artist {artist}')
                artist = None

                break
            except (TimeoutError, httpx.HTTPError):
                logger.debug('Could not establish connection to Danbooru, trying again in 5s...')
                sleep(5)
        else:
            logger.debug('Could not establish connection to Danbooru. Skip this artist...')
            artist = None

        return artist

    def download_tags(self, query: str = '*', min_post_count: int = 10, limit: int = 100) -> List[dict]:
        """
        Download and return tags from Danbooru.

        This method downloads tags from Danbooru. It builds the request with the provided query, minimum post count,
        and limit, and yields the tags page by page.

        Args:
            query (str, optional): Search for specific tag, accepts wildcard (*). If not specified, download all tags.
                                Defaults to '*'.
            min_post_count (int, optional): The minimum amount of posts the tag should have been used in. Defaults to 10.
            limit (int, optional): The amount of tags that should be downloaded. Start from the most recent ones.
                                Defaults to 100.

        Yields:
            List[dict]: A page of found tags.
        """

        if limit > 1000:
            pages = limit // 1000
        else:
            pages = 1

        for page in range(1, pages + 1):
            params = {
                'search[post_count]': f'>{min_post_count}',
                'search[name_matches]': query,
                'limit': limit,
                'page': page,
            }

            try:
                logger.info(f'Fetching tags from Danbooru, page {page}...')
                tags = self.client.get('/tags.json', params=params).json()
                if not isinstance(tags, list):
                    logger.warning(f'Unexpected Danbooru response on page {page}: {tags!r}')
                    continue
                yield tags
            except Exception as e:
                logger.critical(f'Could not fetch tags: {e}')
