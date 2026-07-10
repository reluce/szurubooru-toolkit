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

from typing import Iterable

from loguru import logger


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

    def add(self, post_id: int | str, related_ids: Iterable[int | str]) -> None:
        """
        Records similarity edges between a post and its known related posts.

        Args:
            post_id (int | str): The post ID.
            related_ids (Iterable[int | str]): IDs of posts related to `post_id`.
        """

        for related_id in related_ids:
            self.edges.append((int(post_id), int(related_id)))

    def reconcile(self, szuru) -> int:
        """
        Computes the transitive closure over all recorded edges and writes the full
        member list to every member of each cluster.

        Args:
            szuru (Szurubooru): The szurubooru client to update posts with.

        Returns:
            int: The number of posts whose relations were updated.
        """

        clusters = cluster(self.edges)
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
