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


def test_collect_sources_dedup_and_join():
    result = collect_sources('foo', 'bar', 'foo')
    assert set(result.split('\n')) == {'foo', 'bar'}


def test_collect_sources_strips_trailing_comma():
    assert collect_sources('foo,') == 'foo'


def test_collect_sources_drops_empty():
    assert collect_sources('', 'foo', None) == 'foo'


def test_get_md5sum():
    # md5('hello') is a well-known digest
    assert get_md5sum(b'hello') == '5d41402abc4b2a76b9719d911017c592'


def test_statistics_accumulates():
    # statistics uses module-level counters; reset them for isolation
    utils.total_tagged = 0
    utils.total_wd_tagger = 0
    utils.total_untagged = 0
    utils.total_skipped = 0

    assert statistics(tagged=1) == (1, 0, 0, 0)
    assert statistics(wd_tagger=2, untagged=3, skipped=4) == (1, 2, 3, 4)
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


def test_download_media_returns_none_when_all_attempts_fail(monkeypatch):
    attempts = []

    def failing_get(*args, **kwargs):
        attempts.append(1)
        raise OSError('connection refused')

    monkeypatch.setattr(utils.httpx, 'get', failing_get)

    assert utils.download_media('http://szuru.local/data/1.jpg', md5='abc') is None
    assert len(attempts) == 2


def test_download_media_retries_once_on_md5_mismatch(monkeypatch):
    responses = [b'corrupt', b'intact']

    class FakeResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    monkeypatch.setattr(utils.httpx, 'get', lambda *a, **k: FakeResponse(responses.pop(0)))

    file = utils.download_media('http://szuru.local/data/1.jpg', md5=get_md5sum(b'intact'))

    assert file == b'intact'
    assert responses == []


@pytest.mark.parametrize(
    'url,expected',
    [
        ('exhentai', 'e-hentai'),  # gallery-dl category, both domains
        ('https://e-hentai.org/g/1234/abcdef1234/', 'e-hentai'),
        ('danbooru', 'danbooru'),
        ('https://cdn.donmai.us/original/ab/cd/abcd1234.jpg', 'danbooru'),
        ('https://some.unknown.site/post/1', None),
        ('https://files.yande.re/image/abc/yande.re%201234.jpg', 'yandere'),
        # The host wins over site names elsewhere in the URL
        ('https://kemono.su/fanbox/user/1/post/2', 'kemono'),
        ('https://c1.kemono.su/data/ab/cd/abcd.png?f=pixiv_1.png', 'kemono'),
        ('https://www.pixiv.net/fanbox/creator/1', 'pixiv'),
    ],
)
def test_get_site(url, expected):
    assert utils.get_site(url) == expected


@pytest.mark.parametrize(
    'tags,safety,expected',
    [
        (['1girl', 'nude'], 'safe', 'sketchy'),  # escalates on match
        (['1girl', 'sex'], 'safe', 'unsafe'),
        (['1girl', 'nude', 'sex'], 'safe', 'unsafe'),  # highest matching level wins
        (['1girl', 'nude'], 'unsafe', 'unsafe'),  # never lowered
        (['1girl'], 'safe', 'safe'),  # no match
    ],
)
def test_apply_safety_overrides(tags, safety, expected):
    overrides = {'sketchy': ['nude', 'see-through'], 'unsafe': ['sex']}

    assert utils.apply_safety_overrides(tags, safety, overrides) == expected


def test_apply_safety_overrides_empty_config_is_noop():
    assert utils.apply_safety_overrides(['nude'], 'safe', {}) == 'safe'


def test_generate_src_e_hentai():
    metadata = {'site': 'e-hentai', 'gid': 4046994, 'token': 'd23b006a6f'}

    assert utils.generate_src(metadata) == 'https://e-hentai.org/g/4046994/d23b006a6f'


def test_convert_rating_danbooru_s_is_sensitive():
    assert convert_rating('s', 'danbooru') == 'sketchy'
    assert convert_rating('s', 'konachan') == 'safe'


def test_download_media_rejects_error_pages(monkeypatch):
    import httpx

    request = httpx.Request('GET', 'http://szuru.local/data/1.jpg')
    monkeypatch.setattr(utils.httpx, 'get', lambda *a, **k: httpx.Response(404, content=b'Not found', request=request))

    assert utils.download_media('http://szuru.local/data/1.jpg') is None


class PrepareConfig:
    credentials = {'pixiv': {'token': 'token'}}
    auto_tagger = {'use_pixiv_tags': True}


def booru_result(rating, tags='tag'):
    from szurubooru_toolkit.boorus import BooruPost

    return [BooruPost(id=1, tags=tags, rating=rating)]


def test_prepare_post_uses_strictest_booru_rating():
    results = {'danbooru': booru_result('explicit'), 'konachan': booru_result('safe')}

    # Whichever order the boorus answered in
    for ordered in (results, dict(reversed(results.items()))):
        _, _, rating = utils.prepare_post(ordered, PrepareConfig)
        assert rating == 'unsafe'


def test_prepare_post_without_ratings_keeps_post_safety():
    _, _, rating = utils.prepare_post({'danbooru': booru_result('')}, PrepareConfig)

    assert not rating


class FakePixiv:
    def __init__(self, token):
        pass

    def get_result(self, url):
        return object()

    def get_tags(self, result):
        return ['オリジナル', '女の子']

    def get_rating(self, result):
        return 'safe'

    @staticmethod
    def extract_pixiv_artist(name):
        return 'some_artist'


@pytest.mark.parametrize('use_pixiv_tags', [True, False])
def test_prepare_post_falls_back_to_raw_pixiv_tags(monkeypatch, use_pixiv_tags):
    from types import SimpleNamespace

    monkeypatch.setattr(utils, 'Pixiv', FakePixiv)
    # Danbooru has no translation for any of the Pixiv tags
    monkeypatch.setattr(utils, 'convert_tags', lambda tags: [])
    config = SimpleNamespace(credentials=PrepareConfig.credentials, auto_tagger={'use_pixiv_tags': use_pixiv_tags})
    pixiv = SimpleNamespace(url='https://www.pixiv.net/artworks/1', author_name='someone')

    tags, _, rating = utils.prepare_post({'pixiv': pixiv}, config)

    expected = ['オリジナル', '女の子', 'some_artist'] if use_pixiv_tags else ['some_artist']
    assert tags == expected
    assert rating == 'safe'
