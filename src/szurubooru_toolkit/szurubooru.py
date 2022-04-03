import json
from base64 import b64encode
from math import ceil

import pyszuru
import requests
from loguru import logger


class Szurubooru:
    """Placeholder"""

    def __init__(self, szuru_url: str, szuru_user: str, szuru_token: str) -> None:
        """Placeholder"""
        logger.debug(f'szuru_user = {szuru_user}')
        self.szuru_url = szuru_url
        logger.debug(f'szuru_url = {self.szuru_url}')
        self.szuru_api_url = szuru_url + '/api'
        logger.debug(f'szuru_api_url = {self.szuru_api_url}')

        token = self.encode_auth_headers(szuru_user, szuru_token)
        self.headers = {'Accept': 'application/json', 'Authorization': 'Token ' + token}

        # Use the api object to interact with pyszuru module
        self.api = pyszuru.API(base_url=szuru_url, username=szuru_user, token=szuru_token)

    def get_posts(self, query):
        """
        Return the found post ids of the supplied query.
        Args:
            query: The user input query
        Returns:
            post_ids: A list of the found post ids
            total: The total amount of posts found
        Raises:
            Exception
        """

        if query.isnumeric():
            query = 'id:' + query
            logger.debug(f'Modified input query to "{query}"')

        try:
            query_url = self.szuru_api_url + '/posts/?query=' + query
            logger.debug(f'Getting post from query_url: {query_url}')

            response_json = requests.get(query_url, headers=self.headers)
            response = response_json.json()
            # logger.debug(f'Got following response: {response}')

            if 'name' in response and response['name'] == 'SearchError':
                logger.critical(f'{response["name"]}: {response["description"]}')
                exit()

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
                        query_url = self.szuru_api_url + '/posts/?offset=' + str(page) + '00&query=' + query
                        results = requests.get(query_url, headers=self.headers).json()['results']

                        for result in results:
                            yield self.parse_post(result)

                # return posts, total
            else:
                logger.info('No posts were found for your query!')
                exit()
        except Exception as e:
            logger.critical(f'Could not process your query: {e}')
            exit()

    def parse_post(self, response):
        # logger.debug(f'Parsing post with input: {response}')
        post = Post()

        post.id = str(response['id'])
        post.source = response['source'] if response['source'] else ''
        content_url = response['contentUrl']
        post.content_url = self.szuru_url + '/' + content_url
        post.version = response['version']
        post.relations = response['relations']

        tags = response['tags']
        post.tags = []

        for tag in tags:
            post.tags.append(tag['names'][0])
        # logger.debug(f'Returning Post object: {post}')

        return post

    def update_post(self, post):
        """
        Set tags on post if any were found. Default source to anonymous and rating to unsafe.
        Args:
            post: A post object
        Raises:
            Exception
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
            logger.warning(f'Could not edit your post: {e}')

    @staticmethod
    def encode_auth_headers(user: str, token: str) -> str:
        return b64encode(f'{user}:{token}'.encode()).decode('ascii')


class Post:
    def __init__(self) -> None:
        self.id: str = None
        self.source: str = None
        self.content_url: str = None
        self.version = None
        self.relations: list = []
        self.tags: list = []

    def __repr__(self):
        source = str(self.source).replace('\n', '\\n')
        return_str = (
            f'Post(id: {self.id}, source: {source}, content_url: {self.content_url}, '
            f'version: {self.version}, relations: {self.relations}, tags: {self.tags}'
        )

        return return_str

    def __call__(self):
        return repr(self)


class SearchError(Exception):
    def __init__(self, message) -> None:
        logger.error(message)
