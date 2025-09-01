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
        """
        Initializes the `szurubooru` and `pyszuru` object with our credentials.

        This method initializes a szurubooru object and sets up the client. It uses the provided szuru_url, szuru_user,
        and szuru_token to authenticate with the Szurubooru API. It also sets up the headers for the requests and
        initializes the pyszuru API object.

        Args:
            szuru_url (str): The base URL of the szurubooru instance.
            szuru_user (str): The szurubooru user which interacts with the API.
            szuru_token (str): The API token from `szuru_user`.

        Returns:
            None
        """

        logger.debug(f'szuru_user = {szuru_user}')
        self.szuru_url = szuru_url
        logger.debug(f'szuru_url = {self.szuru_url}')
        self.szuru_api_url = szuru_url + '/api'
        logger.debug(f'szuru_api_url = {self.szuru_api_url}')

        token = self.encode_auth_headers(szuru_user, szuru_token)
        self.headers = {'Accept': 'application/json', 'Authorization': 'Token ' + token, 'Content-Type': 'application/json'}

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
        """
        Retrieves posts from szurubooru based on a query.

        This method retrieves posts from szurubooru based on a query. If the query is numeric, it modifies the query to
        search by ID. If the query contains a token that is not allowed, it sanitizes the token. It then retrieves the
        posts and yields them one by one. If pagination is enabled, it retrieves all pages of results. If videos are
        enabled, it includes video posts in the results.

        Args:
            query (str): The query to use to retrieve the posts.
            pagination (bool, optional): Whether to retrieve all pages of results. Defaults to True.
            videos (bool, optional): Whether to include video posts in the results. Defaults to False.

        Yields:
            Union[str, Post]: The retrieved posts.

        Raises:
            Exception: If an error occurs while retrieving the posts.
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
                query_params = {'query': query, 'limit': 100}
            else:
                query_params = {'query': f'type:image,animation {query}', 'limit': 100}
            query_url = self.szuru_api_url + '/posts/?' + urllib.parse.urlencode(query_params)
            logger.debug(f'Getting post from query_url: {query_url}')

            response_json = requests.get(query_url, headers=self.headers)
            response = response_json.json()
            # logger.debug(f'Got following response: {response}')

            if 'name' in response and 'Error' in response['name']:
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
                                query_params = {'offset': f'{str(page)}00', 'query': query, 'limit': 100}
                            else:
                                query_params = {'offset': f'{str(page)}00', 'query': f'type:image,animation {query}', 'limit': 100}
                            query_url = self.szuru_api_url + '/posts/?' + urllib.parse.urlencode(query_params)
                        results = requests.get(query_url, headers=self.headers).json()['results']

                        for result in results:
                            yield self.parse_post(result)
        except Exception as e:
            logger.critical(f'Could not process your query: {e}')
            exit()

    def parse_post(self, response: dict) -> Post:
        """
        Parses a post from a Szurubooru API response.

        This method parses a post from a szurubooru API response. It creates a new Post object and sets its attributes
        based on the response. It sets the ID, source, content URL, version, relations, MD5 checksum, type, and safety of
        the post. It also parses the tags of the post and adds them to the Post object.

        Args:
            response (dict): The Szurubooru API response to parse.

        Returns:
            Post: The parsed Post object.
        """

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
        """
        Update the input Post object in szurubooru with its updated metadata values.

        This method updates a post in Szurubooru with its updated metadata values. It constructs a URL to the post in the
        Szurubooru API and a payload with the updated metadata. It then sends a PUT request to the URL with the payload. If
        the request is successful, it logs that the post was updated. If an error occurs, it logs the error and raises an
        exception.

        Args:
            post (Post): The Post object with relevant metadata to update.

        Raises:
            Exception: If an error occurs while updating the post.
        """

        logger.debug(f'Updating following post: {post}')

        query_url = self.szuru_api_url + '/post/' + post.id
        logger.debug(f'Using query_url: {query_url}')

        payload = json.dumps({'version': post.version, 'tags': post.tags, 'source': post.source, 'safety': post.safety})
        logger.debug(f'Using payload: {payload}')

        try:
            response = requests.put(query_url, headers=self.headers, data=payload)
            if response.status_code != 200:
                raise Exception(response.text)
        except Exception as e:
            logger.warning(f'Could not edit your post: {e}')

    @staticmethod
    def encode_auth_headers(user: str, token: str) -> str:
        """
        Encodes the authentication headers for szurubooru.

        This method encodes the authentication headers for szurubooru. It takes a user and a token, concatenates them with
        a colon in between, encodes the result in UTF-8, base64 encodes the result, and then decodes the result in ASCII.
        It returns the final result as a string.

        Args:
            user (str): The szurubooru user.
            token (str): The szurubooru token.

        Returns:
            str: The encoded authentication headers.
        """

        return b64encode(f'{user}:{token}'.encode()).decode('ascii')

    def create_tag(self, tag_name: str, category: str, overwrite: bool = False) -> None:
        """
        Creates a new tag in szurubooru.

        This method creates a new tag in szurubooru. It constructs a URL to the tags endpoint in the szurubooru API and a
        payload with the tag name and category. It then sends a POST request to the URL with the payload. If the request is
        successful, it logs that the tag was created. If an error occurs, it logs the error and raises an exception. If the
        tag already exists and overwrite is True, it updates the category of the existing tag. If the tag already exists
        and overwrite is False, it raises a TagExistsError.

        Args:
            tag_name (str): The name of the tag to create.
            category (str): The category of the tag to create.
            overwrite (bool, optional): Whether to overwrite the category of the tag if it already exists. Defaults to False.

        Raises:
            TagExistsError: If the tag already exists and overwrite is False.
            Exception: If an error occurs while creating the tag.
        """

        query_url = self.szuru_api_url + '/tags'
        logger.debug(f'Using query_url: {query_url}')

        payload = json.dumps({'names': [tag_name], 'category': category})
        logger.debug(f'Using payload: {payload}')

        response = requests.post(query_url, headers=self.headers, data=payload)
        try:
            if 'description' in response.json() and len(response.json()['description']) > 0:
                if 'used by another tag' in response.json()['description']:
                    if overwrite:
                        tag = self.api.getTag(tag_name)
                        if tag.category != category:
                            tag.category = category
                            tag.push()
                    else:
                        raise TagExistsError(response.json()['description'])
                elif 'duplicate key value' in response.json()['description']:
                    raise TagExistsError(response.json()['description'])
                else:
                    raise Exception(response.json()['description'])
        except TypeError:
            pass

    def delete_post(self, post: Post) -> None:
        """
        Deletes a post in szurubooru.

        This method deletes a post in szurubooru. It constructs a URL to the post in the szurubooru API and a payload with
        the post's version. It then sends a DELETE request to the URL with the payload. If the request is successful, it
        logs that the post was deleted. If an error occurs, it logs the error and raises an exception.

        Args:
            post (Post): The Post object to delete.

        Raises:
            Exception: If an error occurs while deleting the post.
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
            logger.warning(f'Could not delete your post: {e}')


class Post:
    """Boilerlate Post object which contains relevant metadata for a szurubooru post."""

    def __init__(self) -> None:
        """
        Initializes a Post object with default attributes.

        This method initializes a Post object with default attributes. It sets the ID, source, content URL, version,
        relations, tags, safety, MD5 checksum, and type of the post to their default values.

        Returns:
            None
        """

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
        """
        Returns a string representation of the Post object.

        This method returns a string representation of the Post object. It includes the ID, source, content URL, version,
        relations, tags, and safety of the post in the string. The source is sanitized to replace newline characters with
        '\\n'. The string is formatted and returned.

        Returns:
            str: A string representation of the Post object.
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
