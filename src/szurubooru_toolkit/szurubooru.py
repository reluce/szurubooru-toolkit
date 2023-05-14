from __future__ import annotations

import json
import urllib
from base64 import b64encode
from math import ceil
from typing import Generator

import pyszuru
import requests
from loguru import logger


class Szurubooru:
    """Handles everything related to szurubooru.

    Where speed is of concern, use the `requests` module to interact with the API directly,
    otherwise use the `pyszuru` module where it's more convenient.
    """

    def __init__(self, szuru_url: str, szuru_user: str, szuru_token: str) -> None:
        """Initializes the `szurubooru` and `pyszuru` object with our credentials.

        Args:
            szuru_url (str): The base URL of the szurubooru instance.
            szuru_user (str): The szurubooru user which interacts with the API.
            szuru_token (str): The API token from `szuru_user`.
        """

        logger.debug(f'szuru_user = {szuru_user}')
        self.szuru_url = szuru_url
        logger.debug(f'szuru_url = {self.szuru_url}')
        self.szuru_api_url = szuru_url + '/api'
        logger.debug(f'szuru_api_url = {self.szuru_api_url}')

        token = self.encode_auth_headers(szuru_user, szuru_token)
        self.headers = {'Accept': 'application/json', 'Authorization': 'Token ' + token}

        # Use the api object to interact with pyszuru module
        self.api = pyszuru.API(base_url=szuru_url, username=szuru_user, token=szuru_token)

        self.allowed_tokens = [
            'ar',
            'area',
            'aspect-ratio',
            'comment',
            'comment-count',
            'comment-date',
            'comment-time',
            'content-checksum',
            'creation-date',
            'creation-time',
            'date',
            'disliked',
            'edit-date',
            'edit-time',
            'fav',
            'fav-count',
            'fav-date',
            'fav-time',
            'feature-count',
            'feature-date',
            'feature-time',
            'file-size',
            'flag',
            'height',
            'id',
            'image-ar',
            'image-area',
            'image-aspect-ratio',
            'image-height',
            'image-width',
            'last-edit-date',
            'last-edit-time',
            'liked',
            'md5',
            'note-count',
            'note-text',
            'pool',
            'rating',
            'relation-count',
            'safety',
            'score',
            'sha1',
            'source',
            'submit',
            'tag',
            'tag-count',
            'time',
            'type',
            'upload',
            'uploader',
            'width',
            'sort',
            'liked',
            'disliked',
            'fav',
            'tumbleweed',
        ]

    def get_posts(
        self,
        query: str,
        pagination: bool = True,
        videos: bool = False,
    ) -> Generator[str | Post, None, None]:
        """Return the found post ids of the supplied query.

        Video files like mp4 or webm will be ignored.

        Args:
            query (str): The szurubooru search query.
            pagination (bool): If the offset should be adjusted when searching through pages.
                Disabling this only makes sense if posts are being deleted.
                This won't behave like real a search limit!
            videos (bool): If mp4 and webms should be included from the search query

        Yields:
            Generator[str | Post, None, None]: Will yield the total amount of search results first, then Post objects.
        """

        if query.isnumeric():
            query = 'id:' + query
            logger.debug(f'Modified input query to "{query}"')

        if ':' in query:
            query_list = query.split()
            for tag in query_list:
                if ':' in tag:
                    token = tag.split(':')[0]
                    if token not in self.allowed_tokens and token not in ['-' + t for t in self.allowed_tokens]:
                        sanitized_tag = tag.replace(':', '\\:')  # noqa W605
                        query = query.replace(tag, sanitized_tag)

        try:
            if videos:
                query_params = {'query': query}
            else:
                query_params = {'query': f'type:image,animation {query}'}
            query_url = self.szuru_api_url + '/posts/?' + urllib.parse.urlencode(query_params)
            logger.debug(f'Getting post from query_url: {query_url}')

            response_json = requests.get(query_url, headers=self.headers)
            response = response_json.json()
            # logger.debug(f'Got following response: {response}')

            if 'name' in response and response['name'] == 'SearchError':
                print('')
                logger.critical(f'{response["name"]}: {response["description"]}')
                raise UnknownTokenError(response['description'])

            total = str(response['total'])
            logger.debug(f'Got a total of {total} results')

            results = response['results']
            # logger.debug(f'Got following results: {results}')
            pages = ceil(int(total) / 100)  # Max posts per pages is 100
            logger.debug(f'Searching across {pages} pages')

            if results:
                yield total

                for result in results:
                    yield self.parse_post(result)

                if pages > 1:
                    for page in range(1, pages + 1):
                        if pagination:
                            if videos:
                                query_params = {'offset': f'{str(page)}00', 'query': query}
                            else:
                                query_params = {'offset': f'{str(page)}00', 'query': f'type:image,animation {query}'}
                            query_url = self.szuru_api_url + '/posts/?' + urllib.parse.urlencode(query_params)
                        results = requests.get(query_url, headers=self.headers).json()['results']

                        for result in results:
                            yield self.parse_post(result)
        except Exception as e:
            logger.critical(f'Could not process your query: {e}')
            exit()

    def parse_post(self, response: dict) -> Post:
        """Parses the dict response from szurubooru and returns a Post object with only the relevant metadata.

        Args:
            response (dict): Response from a szurubooru query.

        Returns:
            Post: Post object with relevant metadata.
        """

        # logger.debug(f'Parsing post with input: {response}')
        post = Post()

        post.id = str(response['id'])
        post.source = response['source'] if response['source'] else ''
        content_url = response['contentUrl']
        post.content_url = self.szuru_url + '/' + content_url
        post.version = response['version']
        post.relations = response['relations']
        post.md5 = response['checksumMD5']
        post.type = response['type']
        post.safety = response['safety']

        tags = response['tags']
        post.tags = []

        for tag in tags:
            post.tags.append(tag['names'][0])
        # logger.debug(f'Returning Post object: {post}')

        return post

    def update_post(self, post: Post) -> None:
        """Update the input Post object in szurubooru with its updated metadata values.

        Args:
            Post: Post object with relevant metadata.
        """

        logger.debug(f'Updating following post: {post}')

        query_url = self.szuru_api_url + '/post/' + post.id
        logger.debug(f'Using query_url: {query_url}')

        payload = json.dumps({'version': post.version, 'tags': post.tags, 'source': post.source, 'safety': post.safety})
        logger.debug(f'Using payload: {payload}')

        try:
            response = requests.put(query_url, headers=self.headers, data=payload)
            if 'description' in response.json():
                raise Exception(response.json()['description'])
        except Exception as e:
            print('')
            logger.warning(f'Could not edit your post: {e}')

    @staticmethod
    def encode_auth_headers(user: str, token: str) -> str:
        """Creates an authentication header from the user and token.

        This header is needed to interact with the szurubooru API.

        Args:
            szuru_user (str): The szurubooru user which interacts with the API.
            szuru_token (str): The API token from `szuru_user`.

        Returns:
            str: The encoded base64 authentication header.
        """

        return b64encode(f'{user}:{token}'.encode()).decode('ascii')

    def create_tag(self, tag_name: str, category: str, overwrite: bool = False) -> None:
        """Create tag in szurubooru.

        Args:
            tag_name (str): The name of the tag to be created.
            category (str): The tag's category (needs to already exist).
            overwrite (bool): If the tag's category should be overwritten.

        Raises:
            Exception: With the error description from the szurubooru API.
        """

        query_url = self.szuru_api_url + '/tags'
        logger.debug(f'Using query_url: {query_url}')

        payload = json.dumps({'names': [tag_name], 'category': category})
        logger.debug(f'Using payload: {payload}')

        response = requests.post(query_url, headers=self.headers, data=payload)
        try:
            if 'description' in response.json():
                if 'used by another tag' in response.json()['description']:
                    if overwrite:
                        tag = self.api.getTag(tag_name)
                        if tag.category != category:
                            tag.category = category
                            tag.push()
                    else:
                        raise TagExistsError(response.json()['description'])
                else:
                    raise Exception(response.json()['description'])
        except TypeError:
            pass

    def delete_post(self, post: Post) -> None:
        """Delete the input Post object in szurubooru. Related posts and tags are kept.

        Args:
            Post: Post object with relevant metadata.
        """

        logger.debug(f'Deleting following post: {post}')

        query_url = self.szuru_api_url + '/post/' + post.id
        logger.debug(f'Using query_url: {query_url}')

        payload = json.dumps({'version': post.version})

        try:
            response = requests.delete(query_url, headers=self.headers, data=payload)
            if 'description' in response.json():
                raise Exception(response.json()['description'])
        except Exception as e:
            print('')
            logger.warning(f'Could not delete your post: {e}')


class Post:
    """Boilerlate Post object which contains relevant metadata for a szurubooru post."""

    def __init__(self) -> None:
        """Initializes a Post object with default attributes."""

        self.id: str = None
        self.source: str = None
        self.content_url: str = None
        self.version = None
        self.relations: list = []
        self.tags: list = []
        self.safety = 'safe'
        self.md5 = None
        self.type = None

    def __repr__(self) -> str:
        """Returns the current attributes of this object.

        Returns:
            str: A formatted string with currently set attributes.
        """

        source = str(self.source).replace('\n', '\\n')
        return_str = (
            f'Post(id: {self.id}, source: {source}, content_url: {self.content_url}, '
            f'version: {self.version}, relations: {self.relations}, tags: {self.tags}, safety: {self.safety}'
        )

        return return_str

    def __call__(self):
        """Calls the repr method on object call."""

        return repr(self)


class SzurubooruError(Exception):
    """Base error class which inherits from Exception."""

    pass


class TagExistsError(SzurubooruError):
    """Raise if the tag already exists."""

    pass


class UnknownTokenError(SzurubooruError):
    """Raise if the search token does not valid."""

    pass
