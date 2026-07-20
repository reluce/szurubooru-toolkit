import pytest

import szurubooru_toolkit


# create_tags reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import create_tags  # noqa: E402
from szurubooru_toolkit.szurubooru import Tag  # noqa: E402
from szurubooru_toolkit.szurubooru import TagExistsError  # noqa: E402
from szurubooru_toolkit.szurubooru import TagNotFoundError  # noqa: E402


class StubSzuru:
    """Szurubooru stand-in keeping tags in a dict."""

    def __init__(self):
        self.tags = {}
        self.updated = []

    def get_tag(self, name):
        if name not in self.tags:
            raise TagNotFoundError('TagNotFoundError', f'Tag "{name}" not found')
        return self.tags[name]

    def create_tag(self, name, category='default', overwrite=False):
        if name in self.tags and not overwrite:
            raise TagExistsError(f'Tag "{name}" already exists')
        self.tags[name] = Tag(names=[name], category=category, version=1)
        return self.tags[name]

    def update_tag(self, tag):
        self.tags[tag.primary_name] = tag
        self.updated.append(tag.primary_name)
        return tag


@pytest.fixture
def szuru(monkeypatch):
    szuru = StubSzuru()
    monkeypatch.setattr(create_tags, 'szuru', szuru)
    monkeypatch.setattr(create_tags, 'config', Config())
    return szuru


def implication_names(tag):
    return [implication.primary_name for implication in tag.implications]


def test_add_implications_creates_missing_implied_tags(szuru):
    szuru.create_tag('slime_girl', 'character')

    create_tags.add_implications('slime_girl', ['monster_girl'], {'monster_girl': 'meta'})

    assert szuru.tags['monster_girl'].category == 'meta'
    assert implication_names(szuru.tags['slime_girl']) == ['monster_girl']


def test_add_implications_merges_with_existing(szuru):
    tag = szuru.create_tag('slime_girl', 'character')
    tag.implications.append(Tag(names=['monster_girl']))
    szuru.create_tag('monster_girl')
    szuru.create_tag('slime')

    create_tags.add_implications('slime_girl', ['monster_girl', 'slime'])

    assert implication_names(szuru.tags['slime_girl']) == ['monster_girl', 'slime']


def test_add_implications_noop_when_all_present(szuru):
    tag = szuru.create_tag('slime_girl', 'character')
    tag.implications.append(Tag(names=['monster_girl']))
    szuru.create_tag('monster_girl')

    create_tags.add_implications('slime_girl', ['monster_girl'])

    assert szuru.updated == []


def test_main_single_tag_with_implications(szuru):
    create_tags.main(tag_name='slime_girl', category='character', implications=['slime', 'monster_girl'])

    assert szuru.tags['slime_girl'].category == 'character'
    assert szuru.tags['slime'].category == 'default'
    assert implication_names(szuru.tags['slime_girl']) == ['slime', 'monster_girl']


def test_main_tag_file_with_implication_columns(szuru, tmp_path):
    tag_file = tmp_path / 'tags.txt'
    tag_file.write_text('slime_girl,character,slime\ncat_girl,character\n')

    create_tags.main(tag_file=str(tag_file))

    assert implication_names(szuru.tags['slime_girl']) == ['slime']
    assert implication_names(szuru.tags['cat_girl']) == []


class StubDanbooru:
    def download_tags(self, query, min_post_count, limit):
        yield [{'name': 'slime_girl', 'category': 4}]

    def get_tag_implications(self, tag_names):
        assert tag_names == ['slime_girl']
        return {'slime_girl': ['monster_girl']}

    def get_tag_categories(self, tag_names):
        assert tag_names == ['monster_girl']
        return {'monster_girl': 0}


def test_main_query_imports_danbooru_implications(szuru, monkeypatch):
    monkeypatch.setattr(szurubooru_toolkit, 'danbooru', StubDanbooru(), raising=False)
    create_tags.config.create_tags['import_implications'] = True

    create_tags.main()

    assert szuru.tags['slime_girl'].category == 'character'
    assert szuru.tags['monster_girl'].category == 'default'
    assert implication_names(szuru.tags['slime_girl']) == ['monster_girl']


def test_main_query_skips_implications_by_default(szuru, monkeypatch):
    monkeypatch.setattr(szurubooru_toolkit, 'danbooru', StubDanbooru(), raising=False)

    create_tags.main()

    assert 'monster_girl' not in szuru.tags
    assert implication_names(szuru.tags['slime_girl']) == []
