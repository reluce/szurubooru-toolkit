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
