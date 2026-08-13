import pytest

from szurubooru_toolkit.scripts.fix_sankaku_sources import extract_post_id
from szurubooru_toolkit.scripts.fix_sankaku_sources import fix_source


MD5 = '7a9fa422507e43705c2ae48b7cde5997'


def resolver(mapping):
    return lambda md5: mapping.get(md5)


@pytest.mark.parametrize(
    'url,expected',
    [
        ('https://chan.sankakucomplex.com/post/show/' + MD5, MD5),
        ('https://chan.sankakucomplex.com/post/show/12345678', '12345678'),
        ('https://chan.sankakucomplex.com/en/posts/9PMw6q1LwRB', '9PMw6q1LwRB'),
        ('https://www.sankakucomplex.com/posts/9PMw6q1LwRB', '9PMw6q1LwRB'),
        ('https://sankakucomplex.com/posts/9PMw6q1LwRB', '9PMw6q1LwRB'),
        ('https://sankaku.app/post/show/9PMw6q1LwRB', '9PMw6q1LwRB'),
        # not post links or not Sankaku chan at all
        ('https://www.sankakucomplex.com/2024/05/13/some-article', None),
        ('https://idol.sankakucomplex.com/post/show/12345', None),
        ('https://chan.sankakucomplex.com/?tags=foo', None),
        ('https://danbooru.donmai.us/posts/123', None),
        ('not a url', None),
    ],
)
def test_extract_post_id(url, expected):
    assert extract_post_id(url) == expected


def test_fix_source_rewrites_md5_and_alnum_urls():
    source = f'https://chan.sankakucomplex.com/post/show/{MD5}\nhttps://sankakucomplex.com/posts/9PMw6q1LwRB'
    fixed, unresolved = fix_source(source, None, resolver({MD5: 'abcDEF12345'}))

    assert fixed == 'https://www.sankakucomplex.com/posts/abcDEF12345\nhttps://www.sankakucomplex.com/posts/9PMw6q1LwRB'
    assert unresolved == 0


def test_fix_source_resolves_legacy_numeric_id_via_post_checksum():
    source = 'https://chan.sankakucomplex.com/post/show/12345678'
    fixed, unresolved = fix_source(source, MD5.upper(), resolver({MD5: 'abcDEF12345'}))

    assert fixed == 'https://www.sankakucomplex.com/posts/abcDEF12345'
    assert unresolved == 0


def test_fix_source_keeps_unresolvable_and_foreign_urls():
    source = 'https://chan.sankakucomplex.com/post/show/12345678\nhttps://danbooru.donmai.us/posts/123'
    fixed, unresolved = fix_source(source, None, resolver({}))

    assert fixed == source
    assert unresolved == 1


def test_fix_source_dedupes_rewritten_urls():
    source = f'https://chan.sankakucomplex.com/post/show/{MD5}\nhttps://www.sankakucomplex.com/posts/abcDEF12345'
    fixed, unresolved = fix_source(source, None, resolver({MD5: 'abcDEF12345'}))

    assert fixed == 'https://www.sankakucomplex.com/posts/abcDEF12345'
    assert unresolved == 0
