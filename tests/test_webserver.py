import threading
from http.server import HTTPServer

import httpx
import pytest

import szurubooru_toolkit


# The webserver imports import_from_url, which reads module-level globals
# normally created by setup_clients(); provide stand-ins for the import.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.scripts import webserver  # noqa: E402


@pytest.fixture
def server(monkeypatch):
    imported = []
    monkeypatch.setattr(webserver, 'import_from_url', lambda urls: imported.extend(urls))
    monkeypatch.setattr(webserver, 'apply_overrides', lambda params: None)

    httpd = HTTPServer(('127.0.0.1', 0), webserver.ToolkitRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{httpd.server_port}', imported
    httpd.shutdown()


@pytest.mark.parametrize('origin', ['chrome-extension://abc', 'moz-extension://abc', None])
def test_extension_and_cli_posts_import(server, origin):
    base, imported = server
    headers = {'Origin': origin} if origin else {}

    response = httpx.post(f'{base}/import-from-url', params={'url': 'https://example.com/1'}, headers=headers)

    assert response.status_code == 200
    assert imported == ['https://example.com/1']


def test_get_does_not_import(server):
    # e.g. <img src="http://localhost:5000/import-from-url?url=..."> on any web page
    base, imported = server

    response = httpx.get(f'{base}/import-from-url', params={'url': 'https://example.com/1'})

    assert response.status_code == 405
    assert imported == []


@pytest.mark.parametrize('path', ['/import-from-url?url=https://example.com/1', '/import-from-all-tabs'])
def test_web_page_origin_is_rejected(server, path):
    base, imported = server

    response = httpx.post(f'{base}{path}', json={'urls': ['https://example.com/1']}, headers={'Origin': 'https://evil.example'})

    assert response.status_code == 403
    assert imported == []


def test_empty_overrides_restore_configured_values(monkeypatch):
    from szurubooru_toolkit.config import Config

    config = Config()
    config.import_from_url.update(cookies='/configured/cookies.txt', range=':50')
    monkeypatch.setattr(webserver, 'config', config)
    monkeypatch.setattr(webserver, '_configured', {})

    webserver.apply_overrides({'cookies': '/tmp/other.txt', 'range': ':1'})
    assert (config.import_from_url['cookies'], config.import_from_url['range']) == ('/tmp/other.txt', ':1')

    # The extensions send empty values once the user clears the fields
    webserver.apply_overrides({'cookies': '', 'range': ''})
    assert (config.import_from_url['cookies'], config.import_from_url['range']) == ('/configured/cookies.txt', ':50')


def test_failed_imports_are_reported(server, monkeypatch):
    base, imported = server

    def flaky_import(urls):
        if urls == ['https://example.com/bad']:
            raise RuntimeError('gallery-dl exploded')
        imported.extend(urls)

    monkeypatch.setattr(webserver, 'import_from_url', flaky_import)

    response = httpx.post(f'{base}/import-from-all-tabs', json={'urls': ['https://example.com/1', 'https://example.com/bad']})
    assert response.text.endswith('Successful: 1, Failed: 1')

    response = httpx.post(f'{base}/import-from-url', params={'url': 'https://example.com/bad'})
    assert response.status_code == 500


def test_import_skips_logger_catch():
    # @logger.catch would swallow every error, so no import could ever be reported as failed
    assert webserver.import_from_url is webserver.import_from_url_script.main.__wrapped__
