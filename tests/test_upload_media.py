from pathlib import Path

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


def test_read_sidecar_tags_prefers_gallery_dl_convention(tmp_path):
    file = tmp_path / 'abc.jpg'
    file.write_bytes(b'file-bytes')
    (tmp_path / 'abc.jpg.txt').write_text('tag1\ntag2\n')
    (tmp_path / 'abc.txt').write_text('other_tag\n')

    assert upload_media.read_sidecar_tags(str(file)) == ['tag1', 'tag2']


def test_read_sidecar_tags_falls_back_to_stem(tmp_path):
    file = tmp_path / 'abc.jpg'
    file.write_bytes(b'file-bytes')
    (tmp_path / 'abc.txt').write_text('tag1\n\n  tag2  \n')

    assert upload_media.read_sidecar_tags(str(file)) == ['tag1', 'tag2']


def test_read_sidecar_tags_without_sidecar(tmp_path):
    file = tmp_path / 'abc.jpg'
    file.write_bytes(b'file-bytes')

    assert upload_media.read_sidecar_tags(str(file)) == []


def test_upload_media_passes_sidecar_tags_and_cleans_up(monkeypatch, tmp_path):
    szuru = StubSzuru()
    wire(monkeypatch, szuru)
    upload_media.config.upload_media['read_sidecar_tags'] = True
    upload_media.config.upload_media['cleanup'] = True
    upload_media.config.upload_media['src_path'] = str(tmp_path)

    file = tmp_path / 'abc.jpg'
    file.write_bytes(b'file-bytes')
    sidecar = tmp_path / 'abc.jpg.txt'
    sidecar.write_text('tag1\ntag2\n')

    captured = {}

    def fake_upload_post(file, file_ext, metadata=None, file_path=None, relations_batch=None, **kwargs):
        captured['metadata'] = metadata
        return True, False

    monkeypatch.setattr(upload_media, 'upload_post', fake_upload_post)

    upload_media.main(src_path=[str(file)])

    assert captured['metadata']['tags'] == ['tag1', 'tag2']
    assert not file.exists()
    assert not sidecar.exists()


def test_upload_media_without_sidecar_keeps_default_tags(monkeypatch, tmp_path):
    szuru = StubSzuru()
    wire(monkeypatch, szuru)
    upload_media.config.upload_media['read_sidecar_tags'] = True

    file = tmp_path / 'abc.jpg'
    file.write_bytes(b'file-bytes')

    captured = {}

    def fake_upload_post(file, file_ext, metadata=None, file_path=None, relations_batch=None, **kwargs):
        captured['metadata'] = metadata
        return True, False

    monkeypatch.setattr(upload_media, 'upload_post', fake_upload_post)

    upload_media.main(src_path=[str(file)])

    # No metadata -> upload_post falls back to the configured default tags
    assert captured['metadata'] is None


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


def test_import_creates_categorized_tags_before_post(monkeypatch):
    from szurubooru_toolkit.szurubooru import TagNotFoundError

    szuru = StubSzuru()
    wire(monkeypatch, szuru)
    upload_media.config.tag_categories['enabled'] = True
    events = []

    def missing(name):
        raise TagNotFoundError('TagNotFound', name)

    szuru.get_tag = missing
    szuru.create_tag = lambda name, category: events.append(('tag', name, category))
    original = szuru.create_post

    def create_post(metadata):
        events.append(('post', metadata['tags']))
        return original(metadata)

    szuru.create_post = create_post
    success, _ = upload_media.upload_post(
        b'file-bytes',
        'jpg',
        metadata={
            'tags': ['hatsune_miku'],
            'tag_categories': {'hatsune_miku': 'character'},
            'safety': 'safe',
            'source': 'https://example.com/post/1',
        },
    )
    assert success
    assert events == [('tag', 'hatsune_miku', 'character'), ('post', ['hatsune_miku'])]


def test_update_tags_if_exists_handles_similar_post_entries(monkeypatch):
    # A too-similar match is a reverse-search entry {'distance', 'post'}, not a post resource
    szuru = StubSzuru(similar_posts=[{'distance': 0.01, 'post': {'id': 7}}])
    wire(monkeypatch, szuru)
    upload_media.config.import_from_url['update_tags_if_exists'] = True
    calls = {}
    monkeypatch.setattr(upload_media, 'ensure_tag_categories', lambda *args: None)
    monkeypatch.setattr(upload_media.tag_posts, 'main', lambda query, **kwargs: calls.setdefault('tag_posts', query))
    monkeypatch.setattr(
        upload_media.auto_tagger,
        'main',
        lambda post_id, **kwargs: calls.setdefault('auto_tagger', post_id) and False,
    )

    metadata = {'tags': ['foo'], 'source': 'https://example.com/7', 'safety': 'safe'}
    success, _ = upload_media.upload_post(b'file-bytes', 'jpg', metadata=metadata)

    assert success
    assert szuru.created == []
    assert calls == {'tag_posts': '7', 'auto_tagger': '7'}


def test_get_files_matches_extensions_case_insensitively(tmp_path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / '.hidden').mkdir()
    for name in ['IMG_0001.JPG', 'sub/b.Png', 'c.jpeg', 'notes.txt', '._IMG_0001.JPG', '.hidden/d.jpg', 'jpg']:
        (tmp_path / name).write_bytes(b'x')

    files = upload_media.get_files(str(tmp_path))

    assert sorted(Path(file).relative_to(tmp_path).as_posix() for file in files) == ['IMG_0001.JPG', 'c.jpeg', 'sub/b.Png']


def test_upload_post_normalizes_uppercase_extension(monkeypatch):
    szuru = StubSzuru()
    wire(monkeypatch, szuru)
    extensions = []
    monkeypatch.setattr(upload_media, 'get_media_token', lambda szuru, media, file_ext: extensions.append(file_ext))

    upload_media.upload_post(b'file-bytes', 'MP4')

    assert extensions == ['mp4']
