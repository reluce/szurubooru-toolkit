import json

import httpx
import pytest

from szurubooru_toolkit.szurubooru import Szurubooru
from szurubooru_toolkit.szurubooru import SzurubooruApiError
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import TagExistsError
from szurubooru_toolkit.szurubooru import TagNotFoundError
from szurubooru_toolkit.szurubooru import UnknownTokenError


BASE_URL = 'http://szuru.local'


def make_post_json(post_id: int, tags: list = None, **overrides) -> dict:
    post = {
        'id': post_id,
        'source': f'https://example.com/{post_id}',
        'contentUrl': f'data/posts/{post_id}.jpg',
        'version': 1,
        'relations': [],
        'checksumMD5': f'md5-{post_id}',
        'type': 'image',
        'safety': 'safe',
        'tags': tags if tags is not None else [{'names': ['tag1', 'alias1'], 'category': 'default', 'usages': 1}],
    }
    post.update(overrides)
    return post


class RecordingClient:
    """Szurubooru client wired to a MockTransport which records every request."""

    def __init__(self, handler):
        self.requests = []

        def recording_handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        self.szuru = Szurubooru(BASE_URL, 'user', 'token', transport=httpx.MockTransport(recording_handler))


def test_auth_header_encoding():
    assert Szurubooru.encode_auth_headers('user', 'token') == 'dXNlcjp0b2tlbg=='


def test_client_sends_token_auth():
    client = RecordingClient(lambda request: httpx.Response(200, json={'total': 0, 'results': []}))
    list(client.szuru.get_posts('foo'))

    assert client.requests[0].headers['Authorization'] == 'Token dXNlcjp0b2tlbg=='


def test_get_posts_yields_total_then_posts():
    def handler(request):
        return httpx.Response(200, json={'total': 2, 'results': [make_post_json(1), make_post_json(2)]})

    client = RecordingClient(handler)
    results = list(client.szuru.get_posts('foo'))

    assert results[0] == '2'
    assert [post.id for post in results[1:]] == ['1', '2']


def test_get_posts_empty_yields_nothing():
    client = RecordingClient(lambda request: httpx.Response(200, json={'total': 0, 'results': []}))
    assert list(client.szuru.get_posts('foo')) == []


def test_get_posts_paginates_without_extra_request():
    def handler(request):
        offset = int(dict(request.url.params).get('offset', 0))
        posts = [make_post_json(offset + i) for i in range(100 if offset < 200 else 50)]
        return httpx.Response(200, json={'total': 250, 'results': posts})

    client = RecordingClient(handler)
    results = list(client.szuru.get_posts('foo'))

    assert results[0] == '250'
    assert len(results) - 1 == 250
    # 250 results at 100 per page must be exactly 3 requests
    assert len(client.requests) == 3
    assert [dict(r.url.params).get('offset') for r in client.requests] == [None, '100', '200']


def test_get_posts_numeric_query_searches_by_id():
    client = RecordingClient(lambda request: httpx.Response(200, json={'total': 0, 'results': []}))
    list(client.szuru.get_posts('123'))

    assert 'id:123' in dict(client.requests[0].url.params)['query']


def test_get_posts_excludes_videos_by_default():
    client = RecordingClient(lambda request: httpx.Response(200, json={'total': 0, 'results': []}))
    list(client.szuru.get_posts('foo'))
    list(client.szuru.get_posts('foo', videos=True))

    assert dict(client.requests[0].url.params)['query'].startswith('type:image,animation ')
    assert not dict(client.requests[1].url.params)['query'].startswith('type:')


def test_get_posts_escapes_unknown_tokens():
    client = RecordingClient(lambda request: httpx.Response(200, json={'total': 0, 'results': []}))
    list(client.szuru.get_posts('foo:bar rating:safe'))

    query = dict(client.requests[0].url.params)['query']
    assert 'foo\\:bar' in query
    assert 'rating:safe' in query


def test_get_posts_raises_unknown_token_error():
    def handler(request):
        return httpx.Response(
            400,
            json={'name': 'SearchError', 'title': 'Search error', 'description': 'SearchError: Unknown named token'},
        )

    client = RecordingClient(handler)
    with pytest.raises(UnknownTokenError):
        list(client.szuru.get_posts('foo'))


def test_parse_post_builds_micro_tags():
    tags = [
        {'names': ['hitori_bocchi', 'bocchi'], 'category': 'character', 'usages': 5},
        {'names': ['solo'], 'category': 'default', 'usages': 100},
    ]

    def handler(request):
        return httpx.Response(200, json={'total': 1, 'results': [make_post_json(1, tags=tags)]})

    client = RecordingClient(handler)
    _, post = list(client.szuru.get_posts('foo'))

    assert post.tags == ['hitori_bocchi', 'solo']
    assert [tag.category for tag in post.micro_tags] == ['character', 'default']
    assert post.content_url == f'{BASE_URL}/data/posts/1.jpg'
    assert post.md5 == 'md5-1'


def test_get_post_by_id():
    def handler(request):
        assert request.url.path == '/api/post/42'
        return httpx.Response(200, json=make_post_json(42))

    client = RecordingClient(handler)
    post = client.szuru.get_post('42')

    assert post.id == '42'


def test_update_post_sends_version():
    def handler(request):
        return httpx.Response(200, json=make_post_json(1))

    client = RecordingClient(handler)
    post = client.szuru.get_post('1')
    post.tags = ['new_tag']
    client.szuru.update_post(post)

    request = client.requests[-1]
    assert request.method == 'PUT'
    assert request.url.path == '/api/post/1'
    payload = json.loads(request.content)
    assert payload['version'] == 1
    assert payload['tags'] == ['new_tag']


def test_update_post_logs_instead_of_raising():
    def handler(request):
        if request.method == 'PUT':
            return httpx.Response(409, json={'name': 'IntegrityError', 'title': 'x', 'description': 'version mismatch'})
        return httpx.Response(200, json=make_post_json(1))

    client = RecordingClient(handler)
    post = client.szuru.get_post('1')
    client.szuru.update_post(post)  # must not raise


def test_get_tag_returns_full_tag():
    def handler(request):
        assert request.url.path == '/api/tag/hitori_bocchi'
        return httpx.Response(
            200,
            json={
                'names': ['hitori_bocchi'],
                'category': 'character',
                'version': 3,
                'implications': [{'names': ['hitoribocchi_no_marumaru_seikatsu'], 'category': 'parody', 'usages': 1}],
                'suggestions': [],
            },
        )

    client = RecordingClient(handler)
    tag = client.szuru.get_tag('hitori_bocchi')

    assert tag.primary_name == 'hitori_bocchi'
    assert tag.category == 'character'
    assert tag.version == 3
    assert [implication.primary_name for implication in tag.implications] == ['hitoribocchi_no_marumaru_seikatsu']


def test_get_tag_quotes_special_chars():
    def handler(request):
        assert request.url.raw_path == b'/api/tag/6%2Bgirls'
        return httpx.Response(200, json={'names': ['6+girls'], 'category': 'default', 'version': 1})

    client = RecordingClient(handler)
    assert client.szuru.get_tag('6+girls').primary_name == '6+girls'


def test_get_tag_not_found():
    def handler(request):
        return httpx.Response(404, json={'name': 'TagNotFoundError', 'title': 'Not found', 'description': 'Tag missing'})

    client = RecordingClient(handler)
    with pytest.raises(TagNotFoundError):
        client.szuru.get_tag('missing')


def test_create_tag_returns_tag():
    def handler(request):
        payload = json.loads(request.content)
        return httpx.Response(200, json={'names': payload['names'], 'category': payload['category'], 'version': 1})

    client = RecordingClient(handler)
    tag = client.szuru.create_tag('new_tag', 'character')

    assert tag.primary_name == 'new_tag'
    assert tag.category == 'character'


@pytest.mark.parametrize(
    'error_json',
    [
        # upstream szurubooru
        {'name': 'TagAlreadyExistsError', 'title': 'x', 'description': 'Tag already exists.'},
        # oxibooru wording
        {'name': 'SzurubooruApiError', 'title': 'x', 'description': 'tag_name already exists'},
        {'name': 'IntegrityError', 'title': 'x', 'description': 'duplicate key value violates unique constraint'},
    ],
)
def test_create_tag_exists_raises(error_json):
    client = RecordingClient(lambda request: httpx.Response(409, json=error_json))
    with pytest.raises(TagExistsError):
        client.szuru.create_tag('existing', 'default')


def test_create_tag_exists_with_overwrite_updates_category():
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(409, json={'name': 'TagAlreadyExistsError', 'title': 'x', 'description': 'exists'})
        if request.method == 'GET':
            return httpx.Response(200, json={'names': ['existing'], 'category': 'default', 'version': 2})
        payload = json.loads(request.content)
        assert payload['version'] == 2
        assert payload['category'] == 'meta'
        return httpx.Response(200, json={'names': ['existing'], 'category': 'meta', 'version': 3})

    client = RecordingClient(handler)
    tag = client.szuru.create_tag('existing', 'meta', overwrite=True)

    assert tag.category == 'meta'
    assert [r.method for r in client.requests] == ['POST', 'GET', 'PUT']


def test_create_tag_exists_with_overwrite_same_category_skips_update():
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(409, json={'name': 'TagAlreadyExistsError', 'title': 'x', 'description': 'exists'})
        return httpx.Response(200, json={'names': ['existing'], 'category': 'meta', 'version': 2})

    client = RecordingClient(handler)
    client.szuru.create_tag('existing', 'meta', overwrite=True)

    assert [r.method for r in client.requests] == ['POST', 'GET']


def test_update_tag_serializes_implications_as_names():
    def handler(request):
        return httpx.Response(
            200,
            json={
                'names': ['character_a'],
                'category': 'character',
                'version': 4,
                'implications': [{'names': ['parody_b'], 'category': 'parody', 'usages': 1}],
                'suggestions': [],
            },
        )

    client = RecordingClient(handler)
    tag = Tag(names=['character_a'], category='character', version=3)
    tag.implications.append(Tag(names=['parody_b'], category='parody'))
    client.szuru.update_tag(tag)

    payload = json.loads(client.requests[0].content)
    assert payload == {
        'version': 3,
        'names': ['character_a'],
        'category': 'character',
        'implications': ['parody_b'],
        'suggestions': [],
    }


def test_upload_temporary_file_multipart():
    def handler(request):
        assert request.url.path == '/api/uploads'
        assert b'image/png' in request.content
        return httpx.Response(200, json={'token': 'upload-token'})

    client = RecordingClient(handler)
    assert client.szuru.upload_temporary_file(b'fake-image', 'png') == 'upload-token'


def test_reverse_search():
    def handler(request):
        assert json.loads(request.content) == {'contentToken': 'upload-token'}
        return httpx.Response(200, json={'exactPost': None, 'similarPosts': [{'distance': 0.1, 'post': {'id': 5}}]})

    client = RecordingClient(handler)
    result = client.szuru.reverse_search('upload-token')

    assert result['exactPost'] is None
    assert result['similarPosts'][0]['post']['id'] == 5


def test_create_post_returns_id():
    def handler(request):
        payload = json.loads(request.content)
        assert payload['contentToken'] == 'upload-token'
        assert payload['relations'] == [3, 4]
        return httpx.Response(200, json={'id': 99})

    client = RecordingClient(handler)
    post_id = client.szuru.create_post({'tags': [], 'safety': 'safe', 'relations': [3, 4], 'contentToken': 'upload-token'})

    assert post_id == 99


def test_update_post_relations_merges_with_existing():
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json=make_post_json(2, relations=[{'id': 1}], version=5))
        payload = json.loads(request.content)
        assert payload == {'version': 5, 'relations': [1, 3]}
        return httpx.Response(200, json=make_post_json(2))

    client = RecordingClient(handler)
    assert client.szuru.update_post_relations(2, {3}) is True
    assert [r.method for r in client.requests] == ['GET', 'PUT']


def test_update_post_relations_noop_when_complete():
    def handler(request):
        return httpx.Response(200, json=make_post_json(3, relations=[{'id': 1}, {'id': 2}]))

    client = RecordingClient(handler)
    assert client.szuru.update_post_relations(3, {1, 2}) is False
    assert [r.method for r in client.requests] == ['GET']


def test_update_post_relations_retries_on_version_conflict():
    state = {'puts': 0}

    def handler(request):
        if request.method == 'GET':
            version = 5 + state['puts']
            return httpx.Response(200, json=make_post_json(2, relations=[], version=version))
        state['puts'] += 1
        if state['puts'] == 1:
            return httpx.Response(
                409,
                json={'name': 'ResourceModifiedError', 'title': 'x', 'description': 'someone else modified this'},
            )
        assert json.loads(request.content)['version'] == 6
        return httpx.Response(200, json=make_post_json(2))

    client = RecordingClient(handler)
    assert client.szuru.update_post_relations(2, {1}) is True
    assert state['puts'] == 2


def test_update_post_relations_raises_on_other_errors():
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json=make_post_json(2))
        return httpx.Response(403, json={'name': 'AuthError', 'title': 'x', 'description': 'insufficient privileges'})

    client = RecordingClient(handler)
    with pytest.raises(SzurubooruApiError):
        client.szuru.update_post_relations(2, {1})
    # No retry on non-conflict errors
    assert [r.method for r in client.requests] == ['GET', 'PUT']


def test_non_json_error_raises_api_error():
    client = RecordingClient(lambda request: httpx.Response(502, text='Bad Gateway'))
    with pytest.raises(SzurubooruApiError) as exc_info:
        client.szuru.get_post('1')

    assert exc_info.value.name == 'HTTP502'
