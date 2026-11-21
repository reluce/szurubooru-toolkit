from types import SimpleNamespace

import pytest

from szurubooru_toolkit.pixiv import Pixiv


def pixiv_result(*tags):
    return SimpleNamespace(illust=SimpleNamespace(tags=[{'name': tag} for tag in tags]))


@pytest.mark.parametrize(('tags', 'expected'), [(['R-18'], 'unsafe'), (['R-18G'], 'unsafe'), (['オリジナル'], 'safe')])
def test_get_rating(tags, expected):
    assert Pixiv.get_rating(None, pixiv_result(*tags)) == expected


def test_get_tags_drops_age_restriction_tags():
    assert Pixiv.get_tags(None, pixiv_result('R-18', 'R-18G', 'オリジナル')) == ['オリジナル']


def test_get_tags_and_rating_handle_deleted_dict_response():
    error_response = {'error': {'user_message': 'Page not found'}}
    assert Pixiv.get_tags(None, error_response) == []
    assert Pixiv.get_rating(None, error_response) == 'safe'


@pytest.mark.parametrize(
    ('url', 'expected_id'),
    [
        ('https://www.pixiv.net/member_illust.php?mode=medium&illust_id=123456', 123456),
        ('https://www.pixiv.net/artworks/987654?ref=foo', 987654),
        ('https://www.pixiv.net/invalid', None),
    ],
)
def test_get_result_parses_artwork_and_query_urls(url, expected_id):
    pixiv = Pixiv.__new__(Pixiv)
    seen = []
    pixiv.client = SimpleNamespace(illust_detail=lambda post_id: seen.append(post_id) or {'illust': {'tags': []}})

    result = pixiv.get_result(url)

    if expected_id is None:
        assert result is None
        assert seen == []
    else:
        assert seen == [expected_id]
        assert result == {'illust': {'tags': []}}
