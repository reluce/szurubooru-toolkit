import httpx
import pytest

from szurubooru_toolkit import sankaku as sankaku_module
from szurubooru_toolkit import utils
from szurubooru_toolkit.config import Config


@pytest.fixture
def make_sankaku(monkeypatch):
    config = Config()
    config.credentials['sankaku'] = {'username': None, 'password': None}
    monkeypatch.setattr(sankaku_module, 'config', config)

    def make(handler):
        return sankaku_module.Sankaku(transport=httpx.MockTransport(handler))

    return make


@pytest.mark.parametrize('status', [401, 429, 503])
def test_search_raises_on_error_responses(make_sankaku, status):
    sankaku = make_sankaku(lambda request: httpx.Response(status, json={'success': False}))

    # Returning None here made the caller treat throttling or an expired token as "no result"
    with pytest.raises(httpx.HTTPStatusError):
        sankaku.search('md5:abc')


def test_throttled_search_is_retried(make_sankaku, monkeypatch):
    responses = [httpx.Response(429, json={}), httpx.Response(200, json=[{'id': 'abc'}])]
    sankaku = make_sankaku(lambda request: responses.pop(0))
    # _search_single_booru uses the client which setup_clients() stores on the package
    monkeypatch.setattr('szurubooru_toolkit.sankaku', sankaku)
    monkeypatch.setattr(utils, 'sleep', lambda seconds: None)

    assert utils._search_single_booru('sankaku', 'md5:abc', 1, 0, {}) == [{'id': 'abc'}]


def test_authenticate_reports_non_json_errors(make_sankaku, monkeypatch):
    monkeypatch.setattr(sankaku_module.httpx, 'post', lambda *a, **k: httpx.Response(502, text='<html>Bad Gateway</html>'))

    with pytest.raises(Exception, match='HTTP 502'):
        make_sankaku(None)._authenticate('user', 'password')
