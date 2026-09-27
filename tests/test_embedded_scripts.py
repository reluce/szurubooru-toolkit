"""auto_tagger and tag_posts run once per file inside upload-media; they must not exit() the process there."""

import pytest

import szurubooru_toolkit


# The scripts read module-level globals normally created by setup_clients();
# provide stand-ins so the modules can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import auto_tagger  # noqa: E402
from szurubooru_toolkit.scripts import tag_posts  # noqa: E402
from szurubooru_toolkit.szurubooru import SzurubooruError  # noqa: E402


class StubSzuru:
    def __init__(self, error=None):
        self.error = error

    def get_posts(self, query, pagination=True, videos=False, max_results=None):
        if self.error:
            raise self.error
        return iter([])


@pytest.fixture
def config(monkeypatch):
    config = Config()
    config.auto_tagger.update(saucenao=False, wd_tagger=False, md5_search=True)
    monkeypatch.setattr(auto_tagger, 'config', config)
    monkeypatch.setattr(tag_posts, 'config', config)
    return config


@pytest.mark.parametrize('error', [None, SzurubooruError('server down')])
def test_auto_tagger_returns_instead_of_exiting_for_upload_media(monkeypatch, config, error):
    monkeypatch.setattr(auto_tagger, 'szuru', StubSzuru(error))

    assert auto_tagger.main(post_id='1', limit_reached=True) is True


def test_auto_tagger_cli_still_exits_on_error(monkeypatch, config):
    monkeypatch.setattr(auto_tagger, 'szuru', StubSzuru(SzurubooruError('server down')))

    with pytest.raises(SystemExit):
        auto_tagger.main(query='foo')


@pytest.mark.parametrize('error', [None, SzurubooruError('server down')])
def test_tag_posts_returns_instead_of_exiting_for_upload_media(monkeypatch, config, error):
    config.tag_posts['silence_info'] = True
    monkeypatch.setattr(tag_posts, 'szuru', StubSzuru(error))

    tag_posts.main(query='1', add_tags=['foo'])
