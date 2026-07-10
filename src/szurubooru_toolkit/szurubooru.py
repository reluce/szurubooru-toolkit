from __future__ import annotations

import urllib.parse
from base64 import b64encode
from math import ceil
from typing import Generator

import httpx
from loguru import logger


_TAG_EXISTS_DESCRIPTIONS = (
    'used by another tag',
    'duplicate key value',
    'tag_name already exists',
)


def _is_tag_exists_error(response_json: dict) -> bool:
    if response_json.get('name') == 'TagAlreadyExistsError':
        return True
    description = response_json.get('description', '')
    return any(phrase in description for phrase in _TAG_EXISTS_DESCRIPTIONS)


class SzurubooruError(Exception):
    """Base error class which inherits from Exception."""

    pass


class SzurubooruApiError(SzurubooruError):
    """Raise if the szurubooru API returned an error response."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        super().__init__(f'{name}: {description}')


class TagNotFoundError(SzurubooruApiError):
    """Raise if the requested tag does not exist."""

    pass


class TagExistsError(SzurubooruError):
    """Raise if the tag already exists."""

    pass


class UnknownTokenError(SzurubooruError):
    """Raise if the search token is not valid."""

    pass


class Tag:
    """Represents a szurubooru tag resource.

    Tags embedded in other resources (posts, implications, suggestions) are "micro tags"
    which only carry names and category. Full tags additionally carry version,
    implications and suggestions and can be pushed back with `Szurubooru.update_tag`.
    """

    def __init__(
        self,
        names: list[str],
        category: str = 'default',
        version: int = None,
        implications: list[Tag] = None,
        suggestions: list[Tag] = None,
    ) -> None:
        self.names = names
        self.category = category
        self.version = version
        self.implications = implications if implications is not None else []
        self.suggestions = suggestions if suggestions is not None else []

    @classmethod
    def from_json(cls, data: dict) -> Tag:
        return cls(
            names=data['names'],
            category=data.get('category', 'default'),
            version=data.get('version'),
            implications=[cls.from_json(tag) for tag in data.get('implications', [])],
            suggestions=[cls.from_json(tag) for tag in data.get('suggestions', [])],
        )

    @property
    def primary_name(self) -> str:
        return self.names[0]

    def __str__(self) -> str:
        return self.primary_name

    def __repr__(self) -> str:
        return f'Tag(names: {self.names}, category: {self.category})'


class Szurubooru:
    """Handles everything related to the szurubooru API.

    Single consolidated client on top of one pooled httpx.Client. Compatible with
    upstream szurubooru and the oxibooru fork.
    """

    def __init__(self, szuru_url: str, szuru_user: str, szuru_token: str, transport: httpx.BaseTransport = None) -> None:
        """
        Initializes the szurubooru client with our credentials.

        Args:
            szuru_url (str): The base URL of the szurubooru instance.
            szuru_user (str): The szurubooru user which interacts with the API.
            szuru_token (str): The API token from `szuru_user`.
            transport (httpx.BaseTransport, optional): Custom transport, used for testing.
        """

        logger.debug(f'szuru_user = {szuru_user}')
        self.szuru_url = szuru_url.rstrip('/')
        logger.debug(f'szuru_url = {self.szuru_url}')
        self.szuru_api_url = self.szuru_url + '/api'
        logger.debug(f'szuru_api_url = {self.szuru_api_url}')

        token = self.encode_auth_headers(szuru_user, szuru_token)
        self.headers = {'Accept': 'application/json', 'Authorization': 'Token ' + token}

        self.client = httpx.Client(
            base_url=self.szuru_api_url,
            headers=self.headers,
            timeout=None,
            transport=transport,
        )

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
            'tumbleweed',
        ]

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """
        Sends a request to the szurubooru API and returns the parsed JSON response.

        Raises a typed SzurubooruError subclass if the API responded with an error
        resource ({name, title, description}) or a non-2xx status.
        """

        response = self.client.request(method, path, **kwargs)

        try:
            data = response.json()
        except ValueError:
            data = None

        if isinstance(data, dict) and isinstance(data.get('name'), str) and 'description' in data and data['name'].endswith('Error'):
            name = data['name']
            description = data['description']
            if name == 'TagNotFoundError':
                raise TagNotFoundError(name, description)
            if name == 'SearchError' or 'Unknown named token' in description:
                raise UnknownTokenError(description)
            raise SzurubooruApiError(name, description)

        if response.is_error:
            raise SzurubooruApiError(f'HTTP{response.status_code}', response.text)

        return data

    def get_posts(
        self,
        query: str,
        pagination: bool = True,
        videos: bool = False,
    ) -> Generator[str | Post, None, None]:
        """
        Retrieves posts from szurubooru based on a query.

        If the query is numeric, it is modified to search by ID. Tokens which szurubooru
        does not know are escaped. The total amount of posts is yielded first as a str,
        followed by the matching Post objects.

        Args:
            query (str): The query to use to retrieve the posts.
            pagination (bool, optional): Whether to retrieve all pages of results. Defaults to True.
            videos (bool, optional): Whether to include video posts in the results. Defaults to False.

        Yields:
            str | Post: The total count first, then the retrieved posts.

        Raises:
            UnknownTokenError: If the query contains a search token szurubooru rejects.
            SzurubooruApiError: If the API returns any other error.
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

        if not videos:
            query = f'type:image,animation {query}'

        params = {'query': query, 'limit': 100}
        logger.debug(f'Getting posts with query params: {params}')

        response = self._request('GET', '/posts/', params=params)

        total = str(response['total'])
        logger.debug(f'Got a total of {total} results')

        results = response['results']
        pages = ceil(int(total) / 100)  # Max posts per page is 100
        logger.debug(f'Searching across {pages} pages')

        if results:
            yield total

            for result in results:
                yield self.parse_post(result)

            if pagination:
                for page in range(1, pages):
                    params['offset'] = page * 100
                    results = self._request('GET', '/posts/', params=params)['results']

                    for result in results:
                        yield self.parse_post(result)

    def parse_post(self, response: dict) -> Post:
        """
        Parses a post from a szurubooru API response.

        Args:
            response (dict): The szurubooru API post resource to parse.

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

        post.micro_tags = [Tag.from_json(tag) for tag in response['tags']]
        post.tags = [tag.primary_name for tag in post.micro_tags]

        return post

    def get_post(self, post_id: str) -> Post:
        """
        Retrieves a single post from szurubooru by its ID.

        Args:
            post_id (str): The ID of the post to retrieve.

        Returns:
            Post: The parsed Post object.
        """

        response = self._request('GET', f'/post/{post_id}')

        return self.parse_post(response)

    def update_post(self, post: Post) -> None:
        """
        Update the input Post object in szurubooru with its updated metadata values.

        Args:
            post (Post): The Post object with relevant metadata to update.
        """

        logger.debug(f'Updating following post: {post}')

        payload = {'version': post.version, 'tags': post.tags, 'source': post.source, 'safety': post.safety}
        logger.debug(f'Using payload: {payload}')

        try:
            self._request('PUT', f'/post/{post.id}', json=payload)
        except (SzurubooruError, httpx.HTTPError) as e:
            logger.warning(f'Could not edit your post: {e}')

    def delete_post(self, post: Post) -> None:
        """
        Deletes a post in szurubooru.

        Args:
            post (Post): The Post object to delete.
        """

        logger.debug(f'Deleting following post: {post}')

        try:
            self._request('DELETE', f'/post/{post.id}', json={'version': post.version})
        except (SzurubooruError, httpx.HTTPError) as e:
            logger.warning(f'Could not delete your post: {e}')

    def get_tag(self, tag_name: str) -> Tag:
        """
        Retrieves a tag from szurubooru by name.

        Args:
            tag_name (str): The name of the tag to retrieve.

        Returns:
            Tag: The parsed Tag object.

        Raises:
            TagNotFoundError: If no tag with that name exists.
        """

        response = self._request('GET', '/tag/' + urllib.parse.quote(str(tag_name), safe=''))

        return Tag.from_json(response)

    def create_tag(self, tag_name: str, category: str = 'default', overwrite: bool = False) -> Tag:
        """
        Creates a new tag in szurubooru.

        If the tag already exists and overwrite is True, the category of the existing tag
        is updated. If the tag already exists and overwrite is False, a TagExistsError is
        raised.

        Args:
            tag_name (str): The name of the tag to create.
            category (str): The category of the tag to create. Defaults to 'default'.
            overwrite (bool, optional): Whether to overwrite the category of the tag if it already exists.

        Returns:
            Tag: The created (or already existing) tag.

        Raises:
            TagExistsError: If the tag already exists and overwrite is False.
        """

        try:
            response = self._request('POST', '/tags', json={'names': [tag_name], 'category': category})
            return Tag.from_json(response)
        except SzurubooruApiError as e:
            if not _is_tag_exists_error({'name': e.name, 'description': e.description}):
                raise

            if overwrite:
                tag = self.get_tag(tag_name)
                if tag.category != category:
                    tag.category = category
                    return self.update_tag(tag)
                return tag

            raise TagExistsError(e.description) from e

    def update_tag(self, tag: Tag) -> Tag:
        """
        Update the input Tag object in szurubooru with its updated values.

        Args:
            tag (Tag): The Tag object to push, must carry a version (i.e. come from get_tag/create_tag).

        Returns:
            Tag: The updated tag as returned by szurubooru.
        """

        payload = {
            'version': tag.version,
            'names': tag.names,
            'category': tag.category,
            'implications': [implication.primary_name for implication in tag.implications],
            'suggestions': [suggestion.primary_name for suggestion in tag.suggestions],
        }

        response = self._request('PUT', '/tag/' + urllib.parse.quote(tag.primary_name, safe=''), json=payload)

        return Tag.from_json(response)

    def upload_temporary_file(self, media: bytes, file_ext: str = None) -> str:
        """
        Uploads a media file to the temporary upload endpoint.

        Args:
            media (bytes): The media file to upload as bytes.
            file_ext (str, optional): The file extension to determine the MIME type.

        Returns:
            str: A content token from szurubooru.
        """

        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'webm': 'video/webm',
        }

        if file_ext and file_ext.lower() in mime_types:
            mime_type = mime_types[file_ext.lower()]
            filename = f'file.{file_ext.lower()}'
        else:
            mime_type = 'application/octet-stream'
            filename = 'file'

        response = self._request('POST', '/uploads', files={'content': (filename, media, mime_type)})

        return response['token']

    def reverse_search(self, content_token: str) -> dict:
        """
        Performs a reverse image search with a temporarily uploaded file.

        Args:
            content_token (str): A content token from `upload_temporary_file`.

        Returns:
            dict: The raw response with 'exactPost' and 'similarPosts' keys.
        """

        return self._request('POST', '/posts/reverse-search', json={'contentToken': content_token})

    def create_post(self, metadata: dict) -> str:
        """
        Creates a post in szurubooru from a previously uploaded temporary file.

        Args:
            metadata (dict): The post fields, including the 'contentToken'.

        Returns:
            str: The ID of the created post.
        """

        response = self._request('POST', '/posts', json=metadata)

        return response['id']

    @staticmethod
    def encode_auth_headers(user: str, token: str) -> str:
        """
        Encodes the authentication headers for szurubooru.

        Args:
            user (str): The szurubooru user.
            token (str): The szurubooru token.

        Returns:
            str: The base64 encoded user:token pair.
        """

        return b64encode(f'{user}:{token}'.encode()).decode('ascii')


class Post:
    """Boilerplate Post object which contains relevant metadata for a szurubooru post."""

    def __init__(self) -> None:
        """
        Initializes a Post object with default attributes.
        """

        self.id: str = None
        self.source: str = None
        self.content_url: str = None
        self.version = None
        self.relations: list = []
        self.tags: list = []
        self.micro_tags: list[Tag] = []
        self.safety = 'safe'
        self.md5 = None
        self.type = None

    def __repr__(self) -> str:
        """
        Returns a string representation of the Post object.
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
