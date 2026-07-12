from __future__ import annotations

import threading
from collections import defaultdict

from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.relations import cluster
from szurubooru_toolkit.relations import dhash
from szurubooru_toolkit.relations import hamming_distance
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import run_concurrently


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


def find_duplicate_clusters(hashes: dict[int, int], max_distance: int) -> list[set[int]]:
    """
    Groups posts into duplicate clusters by perceptual hash distance.

    Args:
        hashes (dict[int, int]): Post ids mapped to their perceptual hash.
        max_distance (int): The maximum Hamming distance considered a duplicate.

    Returns:
        list[set[int]]: Clusters of post ids, largest first.
    """

    edges = [
        (post_a, post_b)
        for post_a, post_b in candidate_pairs(hashes, max_distance)
        if hamming_distance(hashes[post_a], hashes[post_b]) <= max_distance
    ]

    return sorted(cluster(edges), key=len, reverse=True)


@logger.catch
def main(query: str = '*') -> None:
    """
    Finds visually duplicate posts by comparing perceptual hashes of their content.

    Downloads the content of every post matching the query, computes a dHash per post
    and clusters posts whose hashes are within the configured Hamming distance. The
    clusters are reported with post URLs; with `set_relations` enabled, the posts of
    each cluster additionally get related to each other in szurubooru.

    Args:
        query (str, optional): The szurubooru query for posts to scan. Defaults to '*'.

    Returns:
        None
    """

    try:
        threshold = int(config.find_duplicates['threshold'])

        logger.info(f'Retrieving posts from {config.globals["url"]} with query "{query}"...')
        posts = szuru.get_posts(query, videos=False)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        if (limit := config.find_duplicates['limit']) and int(limit) > 0 and int(limit) < int(total_posts):
            posts = [next(posts) for _ in range(int(limit))]
            total_posts = len(posts)

        logger.info(f'Found {total_posts} posts. Computing perceptual hashes...')

        hashes: dict[int, int] = {}
        hashes_lock = threading.Lock()

        def worker(post) -> None:
            image_hash = dhash(download_media(post.content_url, post.md5))

            if image_hash is not None:
                with hashes_lock:
                    hashes[int(post.id)] = image_hash
            else:
                logger.debug(f'Could not hash post {post.id}')

        workers = max(1, int(config.find_duplicates['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), config.find_duplicates['hide_progress'])

        clusters = find_duplicate_clusters(hashes, threshold)

        if not clusters:
            logger.success(f'No duplicates found across {len(hashes)} hashed posts (distance <= {threshold}).')
            return

        base_url = config.globals['url']
        logger.success(f'Found {len(clusters)} duplicate set(s) across {len(hashes)} hashed posts (distance <= {threshold}):')

        for members in clusters:
            urls = ', '.join(f'{base_url}/post/{post_id}' for post_id in sorted(members))
            logger.info(f'  {urls}')

        if config.find_duplicates['set_relations']:
            updated = 0
            for members in clusters:
                for post_id in members:
                    try:
                        if szuru.update_post_relations(post_id, members - {post_id}):
                            updated += 1
                    except Exception as e:
                        logger.warning(f'Could not update relations of post {post_id}: {e}')

            logger.success(f'Updated relations of {updated} post(s).')
        else:
            logger.info('Run again with --set-relations to relate the posts of each set to each other.')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
