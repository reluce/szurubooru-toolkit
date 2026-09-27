import threading

import pytest

import szurubooru_toolkit


# The scripts read module-level globals normally created by setup_clients();
# provide stand-ins so the modules can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.boorus import BooruPost  # noqa: E402
from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.saucenao import SauceNaoCooldown  # noqa: E402
from szurubooru_toolkit.scripts import auto_tagger  # noqa: E402
from szurubooru_toolkit.scripts import tag_posts  # noqa: E402
from szurubooru_toolkit.szurubooru import Post  # noqa: E402
from szurubooru_toolkit.szurubooru import TagNotFoundError  # noqa: E402


class StubSzuru:
    def __init__(self, posts=()):
        self.posts = list(posts)
        self.updated = []

    def get_posts(self, query, pagination=True, videos=False):
        if self.posts:
            yield str(len(self.posts))
            yield from self.posts

    def get_tag(self, name):
        raise TagNotFoundError('TagNotFoundError', f'{name} not found')

    def update_post(self, post):
        self.updated.append(post)


def make_post():
    post = Post()
    post.id, post.tags, post.source, post.safety, post.md5, post.type = '1', ['tagme'], '', 'safe', 'abc', 'image'
    post.content_url = 'http://szuru.local/data/1.jpg'
    return post


@pytest.fixture
def szuru(monkeypatch):
    szuru = StubSzuru()
    config = Config()
    # Config() also reads the local config.toml; pin everything these tests depend on
    config.tag_categories['enabled'] = False
    config.globals['public'] = False
    config.auto_tagger.update(wd_tagger_forced=False, dry_run=False, update_relations=False, safety_overrides={})
    monkeypatch.setattr(auto_tagger, 'szuru', szuru)
    monkeypatch.setattr(auto_tagger, 'config', config)
    return szuru


def run(post, limit_reached=False):
    limit_event = threading.Event()
    if limit_reached:
        limit_event.set()
    auto_tagger.process_post(post, None, SauceNaoCooldown(), limit_event, [], [], '', None)


def test_md5_search_keeps_running_after_saucenao_limit(monkeypatch, szuru):
    auto_tagger.config.auto_tagger.update(saucenao=True, md5_search=True, wd_tagger=False)
    searches = []

    def fake_search(booru, query, *args, **kwargs):
        searches.append(query)
        return {'danbooru': [BooruPost(id=1, tags='megumin', rating='general')]}

    monkeypatch.setattr(auto_tagger, 'search_boorus', fake_search)

    run(make_post(), limit_reached=True)

    assert searches == ['md5:abc']
    assert 'megumin' in szuru.updated[0].tags


def test_failed_download_skips_wd_tagger(monkeypatch, szuru):
    auto_tagger.config.auto_tagger.update(saucenao=False, md5_search=False, wd_tagger=True)

    class ExplodingTagger:
        def tag_image(self, *args):
            raise AssertionError('WD tagger must not run without an image')

    monkeypatch.setattr(auto_tagger, 'wd_tagger', ExplodingTagger())
    monkeypatch.setattr(auto_tagger, 'download_media', lambda url, md5: None)

    run(make_post())

    assert set(szuru.updated[0].tags) == {'tagme'}


def test_tag_posts_update_implications_with_new_tag(monkeypatch):
    szuru = StubSzuru([make_post()])
    config = Config()
    config.tag_posts['update_implications'] = True
    monkeypatch.setattr(tag_posts, 'szuru', szuru)
    monkeypatch.setattr(tag_posts, 'config', config)
    monkeypatch.setattr('szurubooru_toolkit.szuru', szuru)

    tag_posts.main('1', add_tags=['brand_new_tag'])

    assert 'brand_new_tag' in szuru.updated[0].tags
