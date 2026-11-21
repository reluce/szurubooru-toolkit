import pytest

import szurubooru_toolkit

# The scripts read module-level globals normally created by setup_clients();
# provide stand-ins so the modules can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import import_from_booru  # noqa: E402
from szurubooru_toolkit.scripts import import_from_url  # noqa: E402


@pytest.mark.parametrize('wd_tagger', [True, False])
def test_auto_tagger_settings_survive_import_from_url(monkeypatch, tmp_path, wd_tagger):
    config = Config()
    config.import_from_booru['wd_tagger'] = wd_tagger
    # import_from_url's own section must not re-enable SauceNAO or MD5 search
    config.import_from_url['saucenao'] = True
    config.import_from_url['md5_search'] = True
    monkeypatch.setattr(import_from_booru, 'config', config)
    monkeypatch.setattr(import_from_url, 'config', config)
    monkeypatch.setattr(import_from_url, 'invoke_gallery_dl', lambda *args, **kwargs: str(tmp_path))

    import_from_booru.main('danbooru', 'foo')

    assert config.upload_media['auto_tag'] is wd_tagger
    if wd_tagger:
        assert config.auto_tagger['wd_tagger'] is True
        assert config.auto_tagger['saucenao'] is False
        assert config.auto_tagger['md5_search'] is False


def test_single_file_limit_uses_an_inclusive_range(monkeypatch):
    config = Config()
    config.import_from_booru['limit'] = 1
    monkeypatch.setattr(import_from_booru, 'config', config)
    monkeypatch.setattr(import_from_url, 'main', lambda urls: None)

    import_from_booru.main('danbooru', 'foo')

    assert config.import_from_url['range'] == '1-1'


def test_import_from_booru_clears_queue_path_and_encodes_query(monkeypatch):
    config = Config()
    config.import_from_url['queue_path'] = '/tmp/some-queue'
    monkeypatch.setattr(import_from_booru, 'config', config)
    captured = []
    monkeypatch.setattr(import_from_url, 'main', lambda urls: captured.extend(urls))

    import_from_booru.main('gelbooru', 'r&b c++ #tag')

    assert config.import_from_url['queue_path'] is None
    assert captured == ['https://gelbooru.com/index.php?page=post&s=list&tags=r%26b+c%2B%2B+%23tag']
