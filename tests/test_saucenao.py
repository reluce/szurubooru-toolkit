import httpx
import pytest

from szurubooru_toolkit.saucenao import SauceNao


class FakeConfig:
    def __init__(self, token='None'):
        self.auto_tagger = {'saucenao_api_token': token}


def make_saucenao(handler, token='None'):
    sauce = SauceNao(FakeConfig(token), transport=httpx.MockTransport(handler))
    sauce.retry_delay = 0
    return sauce


def saucenao_response(results=None, short_remaining=3, long_remaining=90, status=0, message=None):
    header = {'status': status, 'short_remaining': short_remaining, 'long_remaining': long_remaining}
    if message:
        header['message'] = message
    return {'header': header, 'results': results or []}


def make_result(similarity, ext_urls, **data):
    return {'header': {'similarity': str(similarity), 'index_id': 5}, 'data': {'ext_urls': ext_urls, **data}}


@pytest.mark.parametrize(
    'url,expected',
    [
        ('https://www.pixiv.net/member_illust.php?illust_id=123', 'pixiv'),
        ('https://danbooru.donmai.us/posts/123', 'donmai'),
        ('https://gelbooru.com/index.php?id=1', 'gelbooru'),
        ('https://yande.re/post/show/1', 'yande'),
        ('https://konachan.com/post/show/1', 'konachan'),
        ('https://chan.sankakucomplex.com/post/show/1', 'sankakucomplex'),
        ('https://example.com/foo', 'example'),
    ],
)
def test_get_base_domain(url, expected):
    assert SauceNao.get_base_domain(url) == expected


def test_get_result_filters_by_similarity():
    def handler(request):
        return httpx.Response(
            200,
            json=saucenao_response(
                results=[
                    make_result(95.0, ['https://danbooru.donmai.us/posts/1']),
                    make_result(50.0, ['https://danbooru.donmai.us/posts/2']),
                ],
            ),
        )

    sauce = make_saucenao(handler)
    response = sauce.get_result('http://szuru.local/img.jpg')

    assert len(response) == 1
    assert response.short_remaining == 3
    assert response.long_remaining == 90


def test_get_result_daily_limit_reached():
    def handler(request):
        return httpx.Response(429, json=saucenao_response(long_remaining=0, message='Daily Search Limit Exceeded'))

    sauce = make_saucenao(handler)
    assert sauce.get_result('http://szuru.local/img.jpg') == 'Limit reached'


def test_get_result_retries_on_short_limit():
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(429, json=saucenao_response(short_remaining=0, message='Search Rate Too High'))
        return httpx.Response(200, json=saucenao_response())

    sauce = make_saucenao(handler)
    response = sauce.get_result('http://szuru.local/img.jpg')

    assert len(attempts) == 3
    assert response is not None


def test_get_result_sends_api_key_and_file():
    def handler(request):
        assert dict(request.url.params)['api_key'] == 'secret'
        assert b'fake-image-bytes' in request.read()
        return httpx.Response(200, json=saucenao_response())

    sauce = make_saucenao(handler, token='secret')
    sauce.get_result('http://szuru.local/img.jpg', image=b'fake-image-bytes')


def test_get_metadata_maps_sites():
    def handler(request):
        return httpx.Response(
            200,
            json=saucenao_response(
                results=[
                    make_result(95.0, ['https://danbooru.donmai.us/posts/123']),
                    make_result(92.0, ['https://yande.re/post/show/456']),
                    make_result(90.0, [], pixiv_id=789, member_name='some_artist'),
                ],
            ),
        )

    sauce = make_saucenao(handler)
    matches, short_remaining, long_remaining = sauce.get_metadata('http://szuru.local/img.jpg')

    assert matches['donmai'] == {'site': 'danbooru', 'post_id': 123}
    assert matches['yande'] == {'site': 'yandere', 'post_id': 456}
    assert matches['pixiv'].url == 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=789'
    assert matches['pixiv'].author_name == 'some_artist'
    assert matches['gelbooru'] is None
    assert short_remaining == 3
    assert long_remaining == 90


def test_get_metadata_limit_reached():
    def handler(request):
        return httpx.Response(200, json=saucenao_response(long_remaining=-1, message='Daily Search Limit Exceeded'))

    sauce = make_saucenao(handler)
    matches, _, long_remaining = sauce.get_metadata('http://szuru.local/img.jpg')

    assert long_remaining == 0
    assert all(match is None for match in matches.values())


def test_get_metadata_connection_failure_returns_default_limits():
    def handler(request):
        raise httpx.ConnectError('boom')

    sauce = make_saucenao(handler)
    sauce.retry_attempts = 2
    matches, short_remaining, long_remaining = sauce.get_metadata('http://szuru.local/img.jpg')

    assert all(match is None for match in matches.values())
    assert short_remaining == 1
    assert long_remaining == 1
