from io import BytesIO

import pytest
from PIL import Image

from szurubooru_toolkit import utils
from szurubooru_toolkit.utils import audit_rating
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import convert_rating
from szurubooru_toolkit.utils import get_md5sum
from szurubooru_toolkit.utils import sanitize_tags
from szurubooru_toolkit.utils import shrink_img
from szurubooru_toolkit.utils import statistics


@pytest.mark.parametrize(
    'rating,expected',
    [
        ('Safe', 'safe'),
        ('safe', 'safe'),
        ('s', 'safe'),
        ('g', 'safe'),
        ('Questionable', 'sketchy'),
        ('questionable', 'sketchy'),
        ('q', 'sketchy'),
        ('Explicit', 'unsafe'),
        ('explicit', 'unsafe'),
        ('e', 'unsafe'),
        ('rating:safe', 'safe'),
        ('rating:questionable', 'sketchy'),
        ('rating:explicit', 'unsafe'),
        # full-word ratings as returned by Gelbooru and the in-house booru clients
        ('general', 'safe'),
        ('sensitive', 'sketchy'),
        ('unknown', None),
        ('', None),
    ],
)
def test_convert_rating(rating, expected):
    assert convert_rating(rating) == expected


def test_audit_rating_returns_highest():
    assert audit_rating('safe', 'sketchy', 'unsafe') == 'unsafe'
    assert audit_rating('safe', 'sketchy') == 'sketchy'
    assert audit_rating('safe') == 'safe'


def test_audit_rating_empty_defaults_to_safe():
    assert audit_rating() == 'safe'


def test_audit_rating_skips_falsy_entries():
    assert audit_rating(None, '', 'sketchy') == 'sketchy'


def test_sanitize_tags_replaces_whitespace():
    assert sanitize_tags(['tag 1', 'tag_2', 'a b c']) == ['tag_1', 'tag_2', 'a_b_c']


def test_sanitize_tags_empty():
    assert sanitize_tags([]) == []


def test_collect_sources_dedup_and_join():
    result = collect_sources('foo', 'bar', 'foo')
    assert set(result.split('\n')) == {'foo', 'bar'}


def test_collect_sources_strips_trailing_comma():
    assert collect_sources('foo,') == 'foo'


def test_collect_sources_drops_empty():
    assert collect_sources('', 'foo', None) == 'foo'


def test_collect_sources_empty():
    assert collect_sources() == ''


def test_get_md5sum():
    # md5('hello') is a well-known digest
    assert get_md5sum(b'hello') == '5d41402abc4b2a76b9719d911017c592'


def test_statistics_accumulates():
    # statistics uses module-level counters; reset them for isolation
    utils.total_tagged = 0
    utils.total_deepbooru = 0
    utils.total_untagged = 0
    utils.total_skipped = 0

    assert statistics(tagged=1) == (1, 0, 0, 0)
    assert statistics(deepbooru=2, untagged=3, skipped=4) == (1, 2, 3, 4)
    assert statistics() == (1, 2, 3, 4)


def _make_png(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new('RGB', (width, height), color=(255, 0, 0)).save(buffer, format='PNG')
    return buffer.getvalue()


def test_shrink_img_resize_caps_dimensions():
    image = shrink_img(_make_png(1500, 500), resize=True)
    with Image.open(BytesIO(image)) as img:
        assert max(img.size) <= 1000


def test_shrink_img_convert_returns_jpeg():
    image = shrink_img(_make_png(100, 100), convert=True)
    with Image.open(BytesIO(image)) as img:
        assert img.format == 'JPEG'


def test_shrink_img_noop_returns_original_bytes():
    original = _make_png(100, 100)
    assert shrink_img(original) == original


def test_shrink_img_threshold_shrinks_only_above():
    original = _make_png(200, 200)
    shrunk = shrink_img(original, shrink_threshold=10000, shrink_dimensions=(100, 100))
    with Image.open(BytesIO(shrunk)) as img:
        assert max(img.size) <= 100

    untouched = shrink_img(original, shrink_threshold=1000000, shrink_dimensions=(100, 100))
    assert untouched == original
