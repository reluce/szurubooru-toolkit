from types import SimpleNamespace

import pytest

import szurubooru_toolkit

# import_from_url reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import import_from_url  # noqa: E402


def test_set_tags_extracts_e_hentai_artist(monkeypatch):
    # The canonical artist lookup goes through Danbooru/szurubooru; stub it out
    monkeypatch.setattr(import_from_url.Pixiv, 'extract_pixiv_artist', staticmethod(lambda artist: artist))

    metadata = {
        'site': 'e-hentai',
        'tags': ['artist:some artist', 'male:furry', 'other:full color'],
    }

    tags = import_from_url.set_tags(metadata)

    # namespaced e-hentai tags aren't imported as post tags, but the artist is
    assert tags == ['some_artist']


def test_set_tags_unknown_site_yields_no_tags():
    metadata = {'site': None, 'tags': ['artist:someone']}

    assert import_from_url.set_tags(metadata) == []


@pytest.mark.parametrize('categorize', [False, True])
def test_gelbooru_credentials_passed_to_gallery_dl(monkeypatch, categorize):
    class Cfg:
        globals = {'hide_progress': True}
        import_from_url = {
            'wd_tagger': False,
            'md5_search': False,
            'saucenao': False,
            'cookies': None,
            'range': ':1',
            'tmp_path': '/tmp/import',
            'workers': 1,
        }
        upload_media = {}
        auto_tagger = {}
        tag_categories = {'enabled': categorize}
        credentials = {'gelbooru': {'user_id': '123', 'api_key': 'abc'}}

    monkeypatch.setattr(import_from_url, 'config', Cfg)

    captured = {}

    def fake_invoke(urls, tmp_path, params, workers=1):
        captured['params'] = params
        raise RuntimeError('stop after building params')  # swallowed by @logger.catch

    monkeypatch.setattr(import_from_url, 'invoke_gallery_dl', fake_invoke)

    import_from_url.main(urls=['https://gelbooru.com/index.php?page=post&s=list&tags=x'])

    assert '--option=extractor.gelbooru.user-id=123' in captured['params']
    assert '--option=extractor.gelbooru.api-key=abc' in captured['params']

    assert ('--option=extractor.gelbooru.tags=true' in captured['params']) is categorize


def test_already_uploaded_queries_checksum(monkeypatch):
    queries = []

    class Szuru:
        def get_posts(self, query, **kwargs):
            queries.append(query)
            if query.endswith('a9993e364706816aba3e25717850c26c9cd0d89d'):  # sha1('abc')
                yield '1'

    monkeypatch.setattr(import_from_url, 'szuru', Szuru())

    assert import_from_url.already_uploaded(b'abc') is True
    assert import_from_url.already_uploaded(b'other') is False
    assert queries[0] == 'content-checksum:a9993e364706816aba3e25717850c26c9cd0d89d'


def test_persistent_queue_retries_failed_upload_when_refresh_fails(monkeypatch, tmp_path):
    config = Config()
    config.globals['hide_progress'] = True
    config.import_from_url.update(queue_path=str(tmp_path), workers=1)
    monkeypatch.setattr(import_from_url, 'config', config)
    monkeypatch.setattr(import_from_url, 'already_uploaded', lambda content: content == b'already present')
    monkeypatch.setattr(import_from_url, 'generate_src', lambda metadata: 'https://x.com/user/status/123')
    monkeypatch.setattr(import_from_url.RelationsBatch, 'reconcile', lambda *args: None)
    pending = tmp_path / 'pending'
    downloads = 0
    attempts = []

    def download(cmd):
        nonlocal downloads
        assert f'--download-archive={tmp_path / "archive.sqlite3"}' in cmd
        assert 'archive-event=after,skip' in cmd
        downloads += 1
        if downloads > 1:
            return SimpleNamespace(returncode=4)
        for name, content in [('abc.jpg', b'new image'), ('existing.jpg', b'already present')]:
            (pending / name).write_bytes(content)
            (pending / f'{name}.json').write_text('{"category":"twitter"}')
        (pending / 'partial.jpg.part').write_bytes(b'partial')
        return SimpleNamespace(returncode=0)

    def upload(**kwargs):
        attempts.append(kwargs['file_to_upload'])
        return len(attempts) > 1

    monkeypatch.setattr(import_from_url.subprocess, 'run', download)
    monkeypatch.setattr(import_from_url.upload_media, 'main', upload)
    monkeypatch.setattr(import_from_url, 'extract_twitter_artist', lambda metadata: (None, None))

    urls = ['https://x.com/user/likes']
    with pytest.raises(SystemExit) as first:
        import_from_url.main(urls=urls)
    assert first.value.code == 1
    assert sorted(path.name for path in pending.iterdir()) == ['abc.jpg', 'abc.jpg.json', 'partial.jpg.part']

    with pytest.raises(SystemExit) as second:
        import_from_url.main(urls=urls)
    assert second.value.code == 1
    assert attempts == [b'new image', b'new image']
    assert sorted(path.name for path in pending.iterdir()) == ['partial.jpg.part']
