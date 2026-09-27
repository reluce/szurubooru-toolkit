import szurubooru_toolkit


# delete_posts reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.config import Config  # noqa: E402
from szurubooru_toolkit.scripts import delete_posts  # noqa: E402
from szurubooru_toolkit.szurubooru import Post  # noqa: E402


class StubSzuru:
    def __init__(self, total):
        self.total = total
        self.deleted = []

    def get_posts(self, query, pagination=True, videos=False):
        yield str(self.total)
        # Like the real client: without pagination only the first page (100 posts) comes back
        for post_id in range(self.total if pagination else min(self.total, 100)):
            post = Post()
            post.id = str(post_id)
            yield post

    def delete_post(self, post):
        self.deleted.append(post.id)


def test_deletes_every_matching_post_across_pages(monkeypatch):
    szuru = StubSzuru(250)
    monkeypatch.setattr(delete_posts, 'szuru', szuru)
    monkeypatch.setattr(delete_posts, 'config', Config())

    delete_posts.main('foo', except_ids=['3'])

    assert sorted(szuru.deleted, key=int) == [str(i) for i in range(250) if i != 3]
