"""Post relation clustering and reconciliation.

Relations in szurubooru link visually related posts (e.g. variations of the same
image set). When posts are uploaded one by one, each new post only knows about the
posts that existed at its upload time: post 2 references post 1, post 3 references
posts 1 and 2, but post 2 never learns about post 3.

This module fixes that by treating relations as similarity *edges*, computing the
transitive closure over them (union-find), and writing the complete member list to
every member of each set.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Iterable

from loguru import logger
from PIL import Image

# Maximum Hamming distance between two dHashes (64 bit) to consider posts related.
# Image-set variants with small differences typically stay well below this.
PHASH_THRESHOLD = 8


def dhash(image: bytes, hash_size: int = 8) -> int | None:
    """
    Computes the difference hash (dHash) of an image.

    The image is grayscaled, resized to (hash_size+1) x hash_size and each pixel is
    compared to its right neighbor, giving a hash_size^2 bit fingerprint. Visually
    similar images produce hashes with a small Hamming distance.

    Args:
        image (bytes): The image content.
        hash_size (int, optional): Rows/columns of the hash grid. Defaults to 8 (64 bit hash).

    Returns:
        int | None: The hash, or None if the content is not a decodable image.
    """

    try:
        with Image.open(BytesIO(image)) as img:
            # Lets JPEGs decode in grayscale at up to 1/8 scale; plenty for a 9x8 grid
            img.draft('L', ((hash_size + 1) * 8, hash_size * 8))
            pixels = list(img.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS).tobytes())
    except Exception:
        return None

    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            bits = (bits << 1) | (left > right)

    return bits


def hamming_distance(a: int, b: int) -> int:
    """Returns the number of differing bits between two hashes."""

    return (a ^ b).bit_count()


def candidate_pairs(hashes: dict[int, int], max_distance: int, hash_bits: int = 64) -> set[tuple[int, int]]:
    """
    Returns the post id pairs whose hashes could be within `max_distance` bits.

    Uses the pigeonhole principle: the hash is split into `max_distance + 1` disjoint
    bit bands, and two hashes within `max_distance` must be identical in at least one
    band. Only pairs sharing a band value get an exact Hamming check later, which
    avoids the full O(n²) comparison over all posts.

    Args:
        hashes (dict[int, int]): Post ids mapped to their perceptual hash.
        max_distance (int): The maximum Hamming distance considered a duplicate.
        hash_bits (int, optional): The hash width in bits. Defaults to 64.

    Returns:
        set[tuple[int, int]]: Candidate post id pairs (smaller id first).
    """

    bands = max_distance + 1
    band_bits = hash_bits // bands

    if band_bits == 0:
        # Degenerate case: more bands than bits, fall back to all pairs
        ids = list(hashes)
        return {(min(a, b), max(a, b)) for index, a in enumerate(ids) for b in ids[index + 1 :]}

    buckets = defaultdict(list)

    for post_id, post_hash in hashes.items():
        for band in range(bands):
            band_value = (post_hash >> (band * band_bits)) & ((1 << band_bits) - 1)
            buckets[(band, band_value)].append(post_id)

    pairs = set()
    for members in buckets.values():
        if len(members) > 1:
            for index, post_a in enumerate(members):
                for post_b in members[index + 1 :]:
                    pairs.add((min(post_a, post_b), max(post_a, post_b)))

    return pairs


class UnionFind:
    """Disjoint set structure with path compression."""

    def __init__(self) -> None:
        self.parent = {}

    def find(self, item: int) -> int:
        # Iterative, since long chains of related posts would exceed the recursion limit
        root = self.parent.setdefault(item, item)
        while self.parent[root] != root:
            root = self.parent[root]

        while item != root:
            next_item = self.parent[item]
            self.parent[item] = root
            item = next_item

        return root

    def union(self, a: int, b: int) -> None:
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a != root_b:
            self.parent[root_b] = root_a


def cluster(edges: Iterable[tuple[int, int]]) -> list[set[int]]:
    """
    Groups related post IDs into clusters via transitive closure.

    Args:
        edges (Iterable[tuple[int, int]]): Pairs of related post IDs.

    Returns:
        list[set[int]]: One set of post IDs per connected component (only components
            with at least two members).
    """

    union_find = UnionFind()

    for a, b in edges:
        union_find.union(a, b)

    clusters = {}
    for item in union_find.parent:
        clusters.setdefault(union_find.find(item), set()).add(item)

    return [members for members in clusters.values() if len(members) > 1]


class RelationsBatch:
    """Collects similarity edges during a batch operation and reconciles them at the end.

    Usage: call `add()` for every processed post with the related post IDs known at
    that time, then call `reconcile()` once the batch is complete. Every post of each
    resulting cluster gets the full member list written to its relations.
    """

    def __init__(self) -> None:
        self.edges: list[tuple[int, int]] = []
        self.hashes: dict[int, int] = {}

    def add(self, post_id: int | str, related_ids: Iterable[int | str]) -> None:
        """
        Records similarity edges between a post and its known related posts.

        Args:
            post_id (int | str): The post ID.
            related_ids (Iterable[int | str]): IDs of posts related to `post_id`.
        """

        for related_id in related_ids:
            self.edges.append((int(post_id), int(related_id)))

    def add_hash(self, post_id: int | str, image_hash: int | None) -> None:
        """
        Records the perceptual hash of an uploaded post.

        Posts whose hashes are within PHASH_THRESHOLD of each other are treated as
        related during reconciliation. This catches similarity between posts uploaded
        concurrently, which cannot see each other in the server-side reverse search.

        Args:
            post_id (int | str): The post ID.
            image_hash (int | None): The dHash of the post content; None entries are ignored.
        """

        if image_hash is not None:
            self.hashes[int(post_id)] = image_hash

    def _hash_edges(self) -> list[tuple[int, int]]:
        return [
            (post_a, post_b)
            for post_a, post_b in candidate_pairs(self.hashes, PHASH_THRESHOLD)
            if hamming_distance(self.hashes[post_a], self.hashes[post_b]) <= PHASH_THRESHOLD
        ]

    def reconcile(self, szuru, workers: int = 4) -> int:
        """
        Computes the transitive closure over all recorded edges (server-side similarity
        plus local perceptual-hash matches) and writes the full member list to every
        member of each cluster.

        Clusters are disjoint, so they get reconciled concurrently; the posts within a
        cluster are updated one after another since szurubooru relations are mutual.

        Args:
            szuru (Szurubooru): The szurubooru client to update posts with.
            workers (int, optional): How many clusters to reconcile concurrently. Defaults to 4.

        Returns:
            int: The number of posts whose relations were updated.
        """

        clusters = cluster(self.edges + self._hash_edges())

        def reconcile_cluster(members: set[int]) -> int:
            logger.debug(f'Reconciling relation set: {sorted(members)}')
            updated = 0
            for post_id in members:
                try:
                    if szuru.update_post_relations(post_id, members - {post_id}):
                        updated += 1
                except Exception as e:
                    logger.warning(f'Could not update relations of post {post_id}: {e}')
            return updated

        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            updated = sum(executor.map(reconcile_cluster, clusters))

        if updated:
            logger.info(f'Updated relations of {updated} post(s) across {len(clusters)} set(s).')

        return updated
