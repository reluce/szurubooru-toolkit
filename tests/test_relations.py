import random
from io import BytesIO

from PIL import Image

from szurubooru_toolkit.relations import PHASH_THRESHOLD
from szurubooru_toolkit.relations import RelationsBatch
from szurubooru_toolkit.relations import cluster
from szurubooru_toolkit.relations import dhash
from szurubooru_toolkit.relations import hamming_distance


def make_noise_image(seed: int, modify_corner: bool = False) -> bytes:
    """Deterministic noise image; optionally with a small changed block (an 'image variant')."""

    rng = random.Random(seed)
    pixels = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(64 * 64)]

    if modify_corner:
        for row in range(8):
            for col in range(8):
                pixels[row * 64 + col] = (255, 255, 255)

    image = Image.new('RGB', (64, 64))
    image.putdata(pixels)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def test_cluster_transitive_chain():
    # 1-2 and 2-3 are similar, 1-3 was never directly linked
    assert cluster([(1, 2), (2, 3)]) == [{1, 2, 3}]


def test_cluster_separate_components():
    clusters = cluster([(1, 2), (10, 11), (11, 12)])

    assert sorted(clusters, key=min) == [{1, 2}, {10, 11, 12}]


def test_cluster_empty():
    assert cluster([]) == []


def test_cluster_long_chain():
    # The exact scenario from sequential uploads: every post only knows its predecessors
    edges = []
    for i in range(2, 11):
        edges.append((i, i - 1))

    assert cluster(edges) == [set(range(1, 11))]


class FakeSzuru:
    """Records update_post_relations calls; returns True (updated) per call."""

    def __init__(self, fail_ids=()):
        self.calls = []
        self.fail_ids = set(fail_ids)

    def update_post_relations(self, post_id, relation_ids):
        if post_id in self.fail_ids:
            raise RuntimeError('boom')
        self.calls.append((post_id, set(relation_ids)))
        return True


def test_batch_reconcile_writes_full_member_list():
    batch = RelationsBatch()
    # Sequential upload scenario: post 102 saw 101, post 103 saw 101 and 102
    batch.add(102, [101])
    batch.add(103, [101, 102])

    fake = FakeSzuru()
    updated = batch.reconcile(fake)

    assert updated == 3
    assert dict(fake.calls) == {
        101: {102, 103},
        102: {101, 103},
        103: {101, 102},
    }


def test_batch_reconcile_no_edges():
    assert RelationsBatch().reconcile(FakeSzuru()) == 0


def test_batch_reconcile_continues_after_error():
    batch = RelationsBatch()
    batch.add(2, [1])
    batch.add(3, [1, 2])

    fake = FakeSzuru(fail_ids={1})
    updated = batch.reconcile(fake)

    # Post 1 failed, the other two must still be updated
    assert updated == 2
    assert {call[0] for call in fake.calls} == {2, 3}


def test_batch_add_accepts_string_ids():
    batch = RelationsBatch()
    batch.add('2', ['1'])

    assert batch.edges == [(2, 1)]


def test_dhash_identical_images():
    image = make_noise_image(seed=1)

    assert dhash(image) == dhash(image)


def test_dhash_variant_is_close():
    original = dhash(make_noise_image(seed=1))
    variant = dhash(make_noise_image(seed=1, modify_corner=True))

    assert hamming_distance(original, variant) <= PHASH_THRESHOLD


def test_dhash_different_images_are_far():
    a = dhash(make_noise_image(seed=1))
    b = dhash(make_noise_image(seed=2))

    assert hamming_distance(a, b) > PHASH_THRESHOLD


def test_dhash_invalid_image_returns_none():
    assert dhash(b'not-an-image') is None


def test_batch_add_hash_ignores_none():
    batch = RelationsBatch()
    batch.add_hash(1, None)

    assert batch.hashes == {}


def test_batch_reconcile_clusters_by_hash():
    # Concurrent upload scenario: reverse search saw nothing, only local
    # perceptual hashes link the variants of the same image set.
    batch = RelationsBatch()
    batch.add_hash(1, dhash(make_noise_image(seed=1)))
    batch.add_hash(2, dhash(make_noise_image(seed=1, modify_corner=True)))
    batch.add_hash(3, dhash(make_noise_image(seed=1)))
    batch.add_hash(4, dhash(make_noise_image(seed=2)))  # unrelated image

    fake = FakeSzuru()
    updated = batch.reconcile(fake)

    assert updated == 3
    assert dict(fake.calls) == {
        1: {2, 3},
        2: {1, 3},
        3: {1, 2},
    }


def test_batch_reconcile_merges_hash_and_server_edges():
    batch = RelationsBatch()
    # Server-side similarity linked 1<->10, local hashes link 1<->2
    batch.add(1, [10])
    batch.add_hash(1, dhash(make_noise_image(seed=1)))
    batch.add_hash(2, dhash(make_noise_image(seed=1, modify_corner=True)))

    fake = FakeSzuru()
    batch.reconcile(fake)

    assert dict(fake.calls) == {
        1: {2, 10},
        2: {1, 10},
        10: {1, 2},
    }
