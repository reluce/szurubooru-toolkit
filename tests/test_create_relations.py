import pytest

import szurubooru_toolkit


# create_relations reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import create_relations  # noqa: E402
from szurubooru_toolkit.szurubooru import Tag  # noqa: E402


class StubSzuru:
    def __init__(self):
        self.queries = []
        self.tags = {}

    def get_posts(self, query, pagination=True, videos=False, max_results=None):
        self.queries.append(query)
        yield '10'

    def get_tag(self, name):
        return self.tags.setdefault(name, Tag([name], 'unused'))

    def update_tag(self, tag):
        pass


@pytest.mark.parametrize('order', [0, 1])
def test_both_directions_of_a_pair_are_related(monkeypatch, order):
    szuru = StubSzuru()
    monkeypatch.setattr(create_relations, 'szuru', szuru)
    monkeypatch.setattr(create_relations, 'config', Config())

    tags = [Tag(['bocchi'], 'character'), Tag(['bocchi_the_rock'], 'series'), Tag(['kita'], 'character')]
    if order:
        tags.reverse()

    found_relations = {}
    # The same tags on a second post must not trigger new queries
    for _ in range(2):
        create_relations.check_found_relations(tags, found_relations)

    implications = lambda name: [t.primary_name for t in szuru.tags[name].implications]  # noqa: E731
    assert implications('bocchi') == ['bocchi_the_rock']
    assert implications('kita') == ['bocchi_the_rock']
    assert sorted(t.primary_name for t in szuru.tags['bocchi_the_rock'].suggestions) == ['bocchi', 'kita']
    # Four relatable directions; character <> character pairs are never queried
    assert len(szuru.queries) == 4


def test_threshold_is_inclusive(monkeypatch):
    # README: relations are created if at least `threshold` posts contain both tags
    szuru = StubSzuru()  # every pair query reports 10 posts
    config = Config()
    config.create_relations['threshold'] = 10
    monkeypatch.setattr(create_relations, 'szuru', szuru)
    monkeypatch.setattr(create_relations, 'config', config)

    create_relations.check_found_relations([Tag(['bocchi'], 'character'), Tag(['bocchi_the_rock'], 'series')], {})

    assert [t.primary_name for t in szuru.tags['bocchi'].implications] == ['bocchi_the_rock']
