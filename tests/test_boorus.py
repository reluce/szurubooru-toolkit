import httpx
import pytest

from szurubooru_toolkit import boorus


def run_search(handler, *args, **kwargs):
    transport = httpx.MockTransport(handler)
    return boorus.search(*args, transport=transport, **kwargs)


def test_unknown_booru_raises():
    with pytest.raises(ValueError):
        boorus.search('nosuchbooru', 'foo')


def test_danbooru_parses_posts_and_filters_banned():
    def handler(request):
        assert request.url.host == 'danbooru.donmai.us'
        assert request.url.path == '/posts.json'
        assert dict(request.url.params)['tags'] == 'megumin'
        return httpx.Response(
            200,
            json=[
                {'id': 1, 'tag_string': 'megumin solo', 'rating': 'g', 'md5': 'abc', 'file_url': 'https://x/1.jpg'},
                {'id': 2, 'tag_string': 'banned', 'rating': 'e', 'is_banned': True},
            ],
        )

    posts = run_search(handler, 'danbooru', 'megumin')

    assert len(posts) == 1
    assert posts[0].id == 1
    assert posts[0].tags == 'megumin solo'
    assert posts[0].rating == 'general'


def test_danbooru_passes_credentials_as_params():
    def handler(request):
        params = dict(request.url.params)
        assert params['login'] == 'user'
        assert params['api_key'] == 'key'
        return httpx.Response(200, json=[])

    run_search(handler, 'danbooru', 'foo', credentials={'login': 'user', 'api_key': 'key'})


def test_gelbooru_parses_wrapped_posts():
    def handler(request):
        params = dict(request.url.params)
        assert request.url.host == 'gelbooru.com'
        assert params['page'] == 'dapi'
        assert params['json'] == '1'
        assert params['pid'] == '0'
        return httpx.Response(
            200,
            json={
                '@attributes': {'count': 1},
                'post': [{'id': 7, 'tags': 'a b', 'rating': 'sensitive', 'md5': 'x', 'file_url': 'https://x/7.png'}],
            },
        )

    posts = run_search(handler, 'gelbooru', 'a', page=0)

    assert posts[0].id == 7
    assert posts[0].rating == 'sensitive'


def test_gelbooru_single_post_dict_and_empty():
    def single(request):
        return httpx.Response(200, json={'@attributes': {'count': 1}, 'post': {'id': 7, 'tags': 'a', 'rating': 'g'}})

    def empty(request):
        return httpx.Response(200, json={'@attributes': {'count': 0}})

    assert len(run_search(single, 'gelbooru', 'a')) == 1
    assert run_search(empty, 'gelbooru', 'a') == []


@pytest.mark.parametrize('booru,host', [('konachan', 'konachan.com'), ('yandere', 'yande.re')])
def test_moebooru_parses_posts(booru, host):
    def handler(request):
        assert request.url.host == host
        return httpx.Response(200, json=[{'id': 3, 'tags': 'tag1 tag2', 'rating': 's', 'md5': 'm', 'file_url': 'u'}])

    posts = run_search(handler, booru, 'tag1')

    assert posts[0].id == 3
    assert posts[0].rating == 'safe'
    assert posts[0].tags == 'tag1 tag2'


def test_http_error_propagates():
    def handler(request):
        return httpx.Response(403, json={})

    with pytest.raises(httpx.HTTPStatusError):
        run_search(handler, 'danbooru', 'foo')


def test_limit_capped_at_100():
    def handler(request):
        assert dict(request.url.params)['limit'] == '100'
        return httpx.Response(200, json=[])

    run_search(handler, 'danbooru', 'foo', limit=500)
