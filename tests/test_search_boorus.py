import threading

import pytest

import szurubooru_toolkit
from szurubooru_toolkit import boorus
from szurubooru_toolkit import utils
from szurubooru_toolkit.utils import search_boorus


# auto_tagger reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.scripts.auto_tagger import image_required  # noqa: E402


class FakeSankaku:
    def __init__(self, result=None, barrier=None):
        self.result = result or []
        self.barrier = barrier
        self.calls = []

    def search(self, query, limit, page):
        self.calls.append(query)
        if self.barrier:
            self.barrier.wait()
        return self.result


@pytest.fixture
def fake_sankaku(monkeypatch):
    fake = FakeSankaku()
    monkeypatch.setattr(szurubooru_toolkit, 'sankaku', fake, raising=False)
    return fake


def test_search_boorus_all_runs_concurrently(monkeypatch, fake_sankaku):
    # danbooru, konachan, yandere + sankaku must run at the same time
    # (gelbooru is skipped without credentials); a barrier of 4 only
    # passes if the searches genuinely overlap.
    barrier = threading.Barrier(4, timeout=5)
    fake_sankaku.barrier = barrier
    fake_sankaku.result = [{'id': 1}]

    def fake_search(booru, query, limit, page, credentials=None):
        barrier.wait()
        return [f'{booru}-result']

    monkeypatch.setattr(boorus, 'search', fake_search)

    results = search_boorus('all', 'md5:abc', 1, 0)

    assert results == {
        'sankaku': [{'id': 1}],
        'danbooru': ['danbooru-result'],
        'konachan': ['konachan-result'],
        'yandere': ['yandere-result'],
    }


def test_search_boorus_gelbooru_needs_credentials(monkeypatch, fake_sankaku):
    searched = []

    def fake_search(booru, query, limit, page, credentials=None):
        searched.append((booru, credentials))
        return []

    monkeypatch.setattr(boorus, 'search', fake_search)

    search_boorus('all', 'md5:abc', 1, 0)
    assert 'gelbooru' not in [booru for booru, _ in searched]

    searched.clear()
    search_boorus('all', 'md5:abc', 1, 0, credentials={'gelbooru': {'api_key': 'k', 'user_id': 'u'}})
    assert ('gelbooru', {'api_key': 'k', 'user_id': 'u'}) in searched


def test_search_boorus_single_booru(monkeypatch):
    def fake_search(booru, query, limit, page, credentials=None):
        return ['post']

    monkeypatch.setattr(boorus, 'search', fake_search)

    assert search_boorus('danbooru', 'md5:abc', 1, 0) == {'danbooru': ['post']}


def test_search_boorus_empty_results_excluded(monkeypatch):
    def fake_search(booru, query, limit, page, credentials=None):
        return []

    monkeypatch.setattr(boorus, 'search', fake_search)

    assert search_boorus('danbooru', 'md5:abc', 1, 0) == {}


def test_search_boorus_one_failure_does_not_abort_others(monkeypatch, fake_sankaku):
    utils.total_skipped = 0

    def fake_search(booru, query, limit, page, credentials=None):
        if booru == 'danbooru':
            raise ValueError('boom')
        return [f'{booru}-result']

    monkeypatch.setattr(boorus, 'search', fake_search)
    # Don't wait 10 rounds of 5s retries for the failing booru
    monkeypatch.setattr(utils, 'sleep', lambda seconds: None)

    results = search_boorus('all', 'md5:abc', 1, 0)

    assert 'danbooru' not in results
    assert set(results) == {'konachan', 'yandere'}


@pytest.mark.parametrize(
    'saucenao,deepbooru,forced,public,is_video,limit_reached,expected',
    [
        # md5-only run: nothing needs the image
        (False, False, False, False, False, False, False),
        # SauceNAO on a private instance needs the image
        (True, False, False, False, False, False, True),
        # SauceNAO on a public instance fetches the URL itself
        (True, False, False, True, False, False, False),
        # Deepbooru always needs the image, even on public instances
        (False, True, False, True, False, False, True),
        (False, False, True, True, False, False, True),
        # Videos are never downloaded
        (True, True, True, False, True, False, False),
        # SauceNAO limit reached and no deepbooru: no download
        (True, False, False, False, False, True, False),
        # Limit reached but deepbooru still runs
        (True, True, False, False, False, True, True),
    ],
)
def test_image_required(saucenao, deepbooru, forced, public, is_video, limit_reached, expected):
    assert image_required(saucenao, deepbooru, forced, public, is_video, limit_reached) is expected
