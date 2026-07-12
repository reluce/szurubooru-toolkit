"""In-house booru search clients, replacing the cunnypy dependency.

Supports the boorus the toolkit actually queries: Danbooru, Gelbooru, Konachan
and Yandere. Sankaku has its own module since it needs authentication.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger


USER_AGENT = 'szurubooru-toolkit (https://github.com/reluce/szurubooru-toolkit)'

# One pooled client for all boorus: connections are kept alive per host, so
# repeated searches skip the TCP/TLS handshake. httpx.Client is thread-safe.
_client = httpx.Client(headers={'User-Agent': USER_AGENT}, follow_redirects=True, timeout=30)

_RATINGS = {
    's': 'safe',
    'q': 'questionable',
    'e': 'explicit',
    'g': 'general',
}


@dataclass
class BooruPost:
    """Normalized booru post carrying the fields the toolkit consumes."""

    id: int
    tags: str  # space-separated tag string
    rating: str
    md5: str = None
    file_url: str = None
    source: str = None


def _normalize_rating(rating: str) -> str:
    return _RATINGS.get(rating, rating)


def _parse_danbooru(data: list) -> list[BooruPost]:
    posts = []

    for post in data:
        if post.get('is_banned'):
            continue
        posts.append(
            BooruPost(
                id=post['id'],
                tags=post.get('tag_string', ''),
                rating=_normalize_rating(post.get('rating', '')),
                md5=post.get('md5'),
                file_url=post.get('file_url'),
                source=post.get('source'),
            ),
        )

    return posts


def _parse_gelbooru(data: dict) -> list[BooruPost]:
    results = data.get('post', [])

    if isinstance(results, dict):
        results = [results]

    return [
        BooruPost(
            id=post['id'],
            tags=post.get('tags', ''),
            rating=_normalize_rating(post.get('rating', '')),
            md5=post.get('md5'),
            file_url=post.get('file_url'),
            source=post.get('source'),
        )
        for post in results
    ]


def _parse_moebooru(data: list) -> list[BooruPost]:
    return [
        BooruPost(
            id=post['id'],
            tags=post.get('tags', ''),
            rating=_normalize_rating(post.get('rating', '')),
            md5=post.get('md5'),
            file_url=post.get('file_url'),
            source=post.get('source'),
        )
        for post in data
    ]


BOORUS = {
    'danbooru': {
        'url': 'https://danbooru.donmai.us/posts.json',
        'page_var': 'page',
        'parse': _parse_danbooru,
    },
    'gelbooru': {
        'url': 'https://gelbooru.com/index.php',
        'page_var': 'pid',
        'params': {'page': 'dapi', 's': 'post', 'q': 'index', 'json': '1'},
        'parse': _parse_gelbooru,
    },
    'konachan': {
        'url': 'https://konachan.com/post.json',
        'page_var': 'page',
        'parse': _parse_moebooru,
    },
    'yandere': {
        'url': 'https://yande.re/post.json',
        'page_var': 'page',
        'parse': _parse_moebooru,
    },
}


def search(
    booru: str,
    query: str,
    limit: int = 100,
    page: int = 1,
    credentials: dict = None,
    transport: httpx.BaseTransport = None,
) -> list[BooruPost]:
    """
    Searches the given booru for posts matching the query.

    Uses a shared pooled client, so consecutive searches reuse connections.

    Args:
        booru (str): One of 'danbooru', 'gelbooru', 'konachan' or 'yandere'.
        query (str): The tag query to search for.
        limit (int, optional): The maximum number of results. Defaults to 100.
        page (int, optional): The result page. Defaults to 1.
        credentials (dict, optional): Booru specific auth params which get passed as
            query params (e.g. {'login': ..., 'api_key': ...} for Danbooru or
            {'api_key': ..., 'user_id': ...} for Gelbooru). Defaults to None.
        transport (httpx.BaseTransport, optional): Custom transport, used for testing.

    Returns:
        list[BooruPost]: The normalized search results.

    Raises:
        ValueError: If the booru is not supported.
        httpx.HTTPStatusError: If the booru responds with an error status.
    """

    if booru not in BOORUS:
        raise ValueError(f'No booru exists with name: {booru}')

    site = BOORUS[booru]

    params = dict(site.get('params', {}))
    params.update({'tags': query, 'limit': min(limit, 100), site['page_var']: page})
    if credentials:
        params.update(credentials)

    if transport is not None:
        client = httpx.Client(headers={'User-Agent': USER_AGENT}, follow_redirects=True, timeout=30, transport=transport)
    else:
        client = _client

    response = client.get(site['url'], params=params)
    response.raise_for_status()

    if not response.text:
        return []

    posts = site['parse'](response.json())
    logger.debug(f'Got {len(posts)} result(s) from {booru} for query "{query}"')

    return posts
