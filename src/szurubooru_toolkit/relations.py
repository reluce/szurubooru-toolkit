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
            pixels = list(img.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS).getdata())
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


class UnionFind:
    """Disjoint set structure with path compression."""

    def __init__(self) -> None:
        self.parent = {}

    def find(self, item: int) -> int:
        root = self.parent.setdefault(item, item)

        if root != item:
            root = self.find(root)
            self.parent[item] = root

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
        entries = list(self.hashes.items())
        edges = []

        for index, (post_a, hash_a) in enumerate(entries):
            for post_b, hash_b in entries[index + 1:]:
                if hamming_distance(hash_a, hash_b) <= PHASH_THRESHOLD:
                    edges.append((post_a, post_b))

        return edges

    def reconcile(self, szuru) -> int:
        """
        Computes the transitive closure over all recorded edges (server-side similarity
        plus local perceptual-hash matches) and writes the full member list to every
        member of each cluster.

        Args:
            szuru (Szurubooru): The szurubooru client to update posts with.

        Returns:
            int: The number of posts whose relations were updated.
        """

        clusters = cluster(self.edges + self._hash_edges())
        updated = 0

        for members in clusters:
            logger.debug(f'Reconciling relation set: {sorted(members)}')
            for post_id in members:
                try:
                    if szuru.update_post_relations(post_id, members - {post_id}):
                        updated += 1
                except Exception as e:
                    logger.warning(f'Could not update relations of post {post_id}: {e}')

        if updated:
            logger.info(f'Updated relations of {updated} post(s) across {len(clusters)} set(s).')

        return updated
