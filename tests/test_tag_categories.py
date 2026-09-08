from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import szurubooru_toolkit
from szurubooru_toolkit.boorus import _parse_danbooru
from szurubooru_toolkit.config import Config
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import TagExistsError
from szurubooru_toolkit.szurubooru import TagNotFoundError
from szurubooru_toolkit.tag_categories import ensure_tag_categories
from szurubooru_toolkit.tag_categories import extract_categories
from szurubooru_toolkit.utils import prepare_post


class Client:
    def __init__(self):
        self.tags = {'existing': Tag(names=['existing', 'alias'], category='Manual')}
        self.created = []
        self.posts = []

    def get_tag(self, name):
        if name == 'alias':
            return self.tags['existing']
        if name not in self.tags:
            raise TagNotFoundError('TagNotFound', name)
        return self.tags[name]

    def create_tag(self, name, category):
        assert name not in self.tags
        self.created.append((name, category))
        self.tags[name] = Tag(names=[name], category=category)

    def update_post(self, post):
        self.posts.append(post)


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setattr('os.path.isfile', lambda path: False)
    config = Config()
    config.tag_categories['enabled'] = True
    config.tag_categories['category_map']['character'] = 'Character'
    return config


def test_source_categories_survive_normalization(config):
    posts = _parse_danbooru(
        [{'id': 1, 'rating': 's', 'tag_string': 'miku solo', 'tag_string_character': 'miku', 'tag_string_general': 'solo'}]
    )
    hints = {}
    tags, _, _ = prepare_post({'danbooru': posts}, config, hints)
    client = Client()
    ensure_tag_categories(client, config, tags, hints)
    assert client.created == [('miku', 'Character'), ('solo', 'default')]


def test_existing_aliases_unknown_and_filtered_tags(config):
    client = Client()
    ensure_tag_categories(
        client, config, ['alias', 'unknown', 'new name'], {'alias': 'character', 'new name': 'character', 'removed': 'character'}
    )
    assert client.created == [('new_name', 'Character')]
    assert client.tags['existing'].category == 'Manual'
    assert 'unknown' not in client.tags


@pytest.mark.parametrize('dry_run,enabled', [(True, True), (False, False)])
def test_disabled_and_dry_run_do_not_access_server(config, dry_run, enabled):
    config.tag_categories['enabled'] = enabled
    ensure_tag_categories(None, config, ['miku'], {'miku': 'character'}, dry_run=dry_run)


def test_workers_create_tag_once(config):
    client = Client()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: ensure_tag_categories(client, config, ['miku'], {'miku': 'character'}), range(30)))
    assert client.created == [('miku', 'Character')]


def test_external_creation_race_preserves_existing_tag(config):
    client = Client()

    def raced(name, category):
        client.tags[name] = Tag(names=[name], category='Manual')
        raise TagExistsError(name)

    client.create_tag = raced
    ensure_tag_categories(client, config, ['miku'], {'miku': 'character'})
    assert client.tags['miku'].category == 'Manual'


def test_optional_lookup_only_fetches_missing_unclassified_tags(config, monkeypatch):
    calls = []

    def lookup(names):
        calls.append(names)
        return {'artist': 1, 'unknown': 99}

    monkeypatch.setattr(szurubooru_toolkit, 'danbooru', SimpleNamespace(get_tag_categories=lookup), raising=False)
    config.tag_categories['lookup_danbooru'] = True
    client = Client()
    ensure_tag_categories(client, config, ['existing', 'miku', 'artist', 'unknown'], {'miku': 'character'})
    assert calls == [['artist', 'unknown']]
    assert client.created == [('artist', 'artist'), ('miku', 'Character')]


def test_gallery_and_sankaku_metadata():
    assert extract_categories({'tags_artist': ['someone'], 'tags_copyright': 'vocaloid', 'tags': [{'tagName': 'miku', 'type': 4}]}) == {
        'someone': 'artist',
        'vocaloid': 'copyright',
        'miku': 'character',
    }


@pytest.mark.parametrize('dry_run', [False, True])
def test_auto_tagger_categorizes_only_final_tags(config, monkeypatch, dry_run):
    monkeypatch.setattr(szurubooru_toolkit, 'szuru', None, raising=False)
    import threading

    from szurubooru_toolkit.scripts import auto_tagger
    from szurubooru_toolkit.szurubooru import Post

    client = Client()
    config.auto_tagger.update(saucenao=False, md5_search=True, wd_tagger=False, dry_run=dry_run)
    monkeypatch.setattr(auto_tagger, 'config', config)
    monkeypatch.setattr(auto_tagger, 'szuru', client)
    posts = _parse_danbooru([{'id': 1, 'rating': 's', 'tag_string': 'miku removed', 'tag_string_character': 'miku removed'}])
    monkeypatch.setattr(auto_tagger, 'search_boorus', lambda *a, **kw: {'danbooru': posts})
    post = Post()
    post.id, post.tags, post.source, post.safety, post.md5, post.type = 1, ['tagme'], '', 'safe', 'abc', 'image'
    auto_tagger.process_post(post, None, None, threading.Event(), [], ['removed'])
    assert client.created == ([] if dry_run else [('miku', 'Character')])
    assert len(client.posts) == (0 if dry_run else 1)
