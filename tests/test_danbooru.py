import httpx

from szurubooru_toolkit.danbooru import Danbooru


def make_danbooru(handler):
    return Danbooru(transport=httpx.MockTransport(handler))


def test_search_artist_direct_hit():
    def handler(request):
        assert request.url.path == '/artists.json'
        assert dict(request.url.params)['search[name]'] == 'someartist'
        return httpx.Response(200, json=[{'name': 'someartist_main'}])

    assert make_danbooru(handler).search_artist('SomeArtist') == 'someartist_main'


def test_search_artist_fallback_to_other_names():
    def handler(request):
        params = dict(request.url.params)
        if 'search[name]' in params:
            return httpx.Response(200, json=[])
        assert params['search[any_other_name_like]'] == 'alias'
        assert params['search[is_deleted]'] == 'false'
        return httpx.Response(200, json=[{'name': 'main_name'}])

    assert make_danbooru(handler).search_artist('alias') == 'main_name'


def test_search_artist_not_found():
    def handler(request):
        return httpx.Response(200, json=[])

    assert make_danbooru(handler).search_artist('unknown') is None


def test_get_other_names_tag_found():
    def handler(request):
        assert request.url.path == '/wiki_pages.json'
        assert dict(request.url.params)['search[other_names_match]'] == 'オリジナル'
        return httpx.Response(200, json=[{'title': 'original'}])

    assert make_danbooru(handler).get_other_names_tag('オリジナル') == 'original'


def test_get_other_names_tag_not_found():
    def handler(request):
        return httpx.Response(200, json=[])

    assert make_danbooru(handler).get_other_names_tag('nope') is None


def test_download_tags_yields_pages():
    def handler(request):
        params = dict(request.url.params)
        assert request.url.path == '/tags.json'
        assert params['search[post_count]'] == '>10'
        assert params['search[name_matches]'] == '*'
        return httpx.Response(200, json=[{'name': 'tag1', 'category': 4}])

    pages = list(make_danbooru(handler).download_tags('*', 10, 100))

    assert pages == [[{'name': 'tag1', 'category': 4}]]


def test_download_tags_skips_unexpected_response():
    def handler(request):
        return httpx.Response(200, json={'success': False, 'message': 'error'})

    assert list(make_danbooru(handler).download_tags('*', 10, 100)) == []
