import threading
import time

import pytest

import szurubooru_toolkit
from szurubooru_toolkit import utils
from szurubooru_toolkit.saucenao import SauceNaoCooldown
from szurubooru_toolkit.szurubooru import Tag
from szurubooru_toolkit.szurubooru import TagNotFoundError
from szurubooru_toolkit.utils import get_cached_implications
from szurubooru_toolkit.utils import run_concurrently
from szurubooru_toolkit.utils import statistics


def test_statistics_thread_safe():
    utils.total_tagged = 0
    utils.total_wd_tagger = 0
    utils.total_untagged = 0
    utils.total_skipped = 0

    def hammer():
        for _ in range(100):
            statistics(tagged=1, wd_tagger=1, untagged=1, skipped=1)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert statistics() == (800, 800, 800, 800)


def test_cooldown_noop_without_trigger():
    cooldown = SauceNaoCooldown()
    start = time.monotonic()
    cooldown.wait()

    assert time.monotonic() - start < 0.05


def test_cooldown_blocks_after_trigger():
    cooldown = SauceNaoCooldown()
    cooldown.trigger(0.3)

    start = time.monotonic()
    cooldown.wait()
    elapsed = time.monotonic() - start

    assert 0.25 <= elapsed < 2


def test_cooldown_keeps_latest_resume_time():
    cooldown = SauceNaoCooldown()
    cooldown.trigger(5)
    cooldown.trigger(0.1)  # must not shorten the pending cooldown

    assert cooldown._resume_at - time.monotonic() > 4


class FakeSzuruTags:
    def __init__(self, implications_by_tag, missing=()):
        self.implications_by_tag = implications_by_tag
        self.missing = set(missing)
        self.get_calls = 0
        self.created = []

    def get_tag(self, name):
        self.get_calls += 1
        if name in self.missing:
            raise TagNotFoundError('TagNotFoundError', f'{name} not found')
        implications = [Tag(names=[implication]) for implication in self.implications_by_tag.get(name, [])]
        return Tag(names=[name], implications=implications)

    def create_tag(self, name, category='default', overwrite=False):
        self.created.append(name)
        return Tag(names=[name])


@pytest.fixture(autouse=True)
def clear_implications_cache():
    utils._implications_cache.clear()
    yield
    utils._implications_cache.clear()


def test_implications_cached_across_calls(monkeypatch):
    fake = FakeSzuruTags({'hitori_bocchi': ['hitoribocchi_no_marumaru_seikatsu']})
    monkeypatch.setattr(szurubooru_toolkit, 'szuru', fake, raising=False)

    first = get_cached_implications('hitori_bocchi')
    second = get_cached_implications('hitori_bocchi')

    assert first == second == ['hitoribocchi_no_marumaru_seikatsu']
    assert fake.get_calls == 1  # second call served from cache


def test_implications_create_missing(monkeypatch):
    fake = FakeSzuruTags({}, missing={'new_tag'})
    monkeypatch.setattr(szurubooru_toolkit, 'szuru', fake, raising=False)

    assert get_cached_implications('new_tag', create_missing=True) == []
    assert fake.created == ['new_tag']


def test_implications_missing_raises_without_create(monkeypatch):
    fake = FakeSzuruTags({}, missing={'nope'})
    monkeypatch.setattr(szurubooru_toolkit, 'szuru', fake, raising=False)

    with pytest.raises(TagNotFoundError):
        get_cached_implications('nope')


@pytest.mark.parametrize('workers', [1, 4])
def test_run_concurrently_processes_all_items(workers):
    results = []
    lock = threading.Lock()

    def worker(item):
        with lock:
            results.append(item)

    run_concurrently(range(20), worker, workers=workers, total=20, hide_progress=True)

    assert sorted(results) == list(range(20))


@pytest.mark.parametrize('workers', [1, 4])
def test_run_concurrently_isolates_errors(workers):
    results = []
    lock = threading.Lock()

    def worker(item):
        if item == 3:
            raise RuntimeError('boom')
        with lock:
            results.append(item)

    run_concurrently(range(6), worker, workers=workers, total=6, hide_progress=True)

    assert sorted(results) == [0, 1, 2, 4, 5]


def test_run_concurrently_actually_parallel():
    barrier = threading.Barrier(4, timeout=5)

    def worker(item):
        # Only passes if 4 workers run simultaneously
        barrier.wait()

    start = time.monotonic()
    run_concurrently(range(4), worker, workers=4, total=4, hide_progress=True)

    assert time.monotonic() - start < 5
