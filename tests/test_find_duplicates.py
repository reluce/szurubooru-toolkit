import szurubooru_toolkit


# find_duplicates reads module-level globals normally created by setup_clients();
# provide stand-ins so the module can be imported in tests.
szurubooru_toolkit.szuru = None
szurubooru_toolkit.config = None

from szurubooru_toolkit.scripts.find_duplicates import candidate_pairs  # noqa: E402
from szurubooru_toolkit.scripts.find_duplicates import find_duplicate_clusters  # noqa: E402


def test_candidate_pairs_finds_close_hashes():
    # Hashes 1 and 2 differ by 2 bits, hash 3 is far away from both
    hashes = {
        1: 0b1111_0000_1111_0000,
        2: 0b1111_0000_1111_0011,
        3: 0b0000_1111_0000_1111,
    }

    pairs = candidate_pairs(hashes, max_distance=4)

    assert (1, 2) in pairs


def test_candidate_pairs_never_misses_within_distance():
    # Pigeonhole guarantee: every pair within max_distance must be a candidate
    base = 0x0123456789ABCDEF
    hashes = {0: base}
    for index in range(1, 9):
        hashes[index] = base ^ ((1 << (index * 7)) | (1 << (index * 3)))  # 2 flipped bits each

    pairs = candidate_pairs(hashes, max_distance=4)

    for index in range(1, 9):
        assert (0, index) in pairs


def test_find_duplicate_clusters_exact_distance_check():
    hashes = {
        1: 0b0000_0000,
        2: 0b0000_0011,  # distance 2 from post 1: duplicate
        3: 0b1111_1111,  # far from both
        4: 0b0000_0111,  # distance 3 from post 1, distance 1 from post 2: same cluster
    }

    clusters = find_duplicate_clusters(hashes, max_distance=3)

    assert clusters == [{1, 2, 4}]


def test_find_duplicate_clusters_transitive():
    # 1-2 and 2-3 are within distance, 1-3 is not: still one cluster via transitivity
    hashes = {
        1: 0b0000_0000,
        2: 0b0000_1111,
        3: 0b1111_1111,
    }

    clusters = find_duplicate_clusters(hashes, max_distance=4)

    assert clusters == [{1, 2, 3}]


def test_find_duplicate_clusters_no_duplicates():
    hashes = {1: 0x0000000000000000, 2: 0xFFFFFFFFFFFFFFFF}

    assert find_duplicate_clusters(hashes, max_distance=8) == []
