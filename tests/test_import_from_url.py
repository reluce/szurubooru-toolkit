import szurubooru_toolkit


# import_from_url reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.scripts import import_from_url  # noqa: E402


def test_set_tags_extracts_e_hentai_artist(monkeypatch):
    # The canonical artist lookup goes through Danbooru/szurubooru; stub it out
    monkeypatch.setattr(import_from_url.Pixiv, 'extract_pixiv_artist', staticmethod(lambda artist: artist))

    metadata = {
        'site': 'e-hentai',
        'tags': ['artist:some artist', 'male:furry', 'other:full color'],
    }

    tags = import_from_url.set_tags(metadata)

    # namespaced e-hentai tags aren't imported as post tags, but the artist is
    assert tags == ['some_artist']


def test_set_tags_unknown_site_yields_no_tags():
    metadata = {'site': None, 'tags': ['artist:someone']}

    assert import_from_url.set_tags(metadata) == []
