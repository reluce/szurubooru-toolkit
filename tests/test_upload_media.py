import szurubooru_toolkit


# upload_media reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import upload_media  # noqa: E402


class StubSzuru:
    """Szurubooru stand-in recording created posts."""

    def __init__(self, exact_post=None, similar_posts=None):
        self.exact_post = exact_post
        self.similar_posts = similar_posts or []
        self.created = []

    def upload_temporary_file(self, media, file_ext=None):
        return 'content-token'

    def reverse_search(self, content_token):
        return {'exactPost': self.exact_post, 'similarPosts': self.similar_posts}

    def create_post(self, metadata):
        self.created.append(metadata)
        return 42


def wire(monkeypatch, szuru):
    monkeypatch.setattr('os.path.isfile', lambda path: False)
    monkeypatch.setattr(upload_media, 'szuru', szuru)
    monkeypatch.setattr(upload_media, 'config', Config())


def test_upload_post_uploads_new_file_and_relates_similar_posts(monkeypatch):
    szuru = StubSzuru(similar_posts=[{'distance': 0.2, 'post': {'id': 7}}])
    wire(monkeypatch, szuru)

    success, _ = upload_media.upload_post(b'file-bytes', 'jpg')

    assert success
    assert len(szuru.created) == 1
    assert szuru.created[0]['relations'] == [7]
    assert szuru.created[0]['contentToken'] == 'content-token'


def test_upload_post_skips_upload_when_too_similar(monkeypatch):
    # default max_similarity 0.95 -> distance below 0.05 is "the same post"
    szuru = StubSzuru(similar_posts=[{'distance': 0.01, 'post': {'id': 7}}])
    wire(monkeypatch, szuru)

    success, _ = upload_media.upload_post(b'file-bytes', 'jpg')

    assert success
    assert szuru.created == []


def test_upload_post_skips_upload_when_exact_match_exists(monkeypatch):
    szuru = StubSzuru(exact_post={'id': 3})
    wire(monkeypatch, szuru)

    success, _ = upload_media.upload_post(b'file-bytes', 'jpg')

    assert success
    assert szuru.created == []


def test_upload_post_bails_without_token_and_skips_reverse_search(monkeypatch):
    # A failed token upload must not cascade into a tokenless reverse search (#78)
    szuru = StubSzuru()

    def failing_upload(media, file_ext=None):
        raise upload_media.SzurubooruError('expected a JSON response, got: proxy error page')

    searched = []
    szuru.upload_temporary_file = failing_upload
    szuru.reverse_search = lambda token: searched.append(token)
    wire(monkeypatch, szuru)

    success, _ = upload_media.upload_post(b'file-bytes', 'jpg')

    assert not success
    assert searched == []
    assert szuru.created == []
