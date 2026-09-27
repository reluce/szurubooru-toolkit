from __future__ import annotations

import re
import urllib.parse
from typing import Callable

import httpx
from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import interrupt_exit


# Sankaku (chan) hosts only — idol.sankakucomplex.com is a different site with its own IDs.
HOSTS = {
    'sankakucomplex.com',
    'www.sankakucomplex.com',
    'chan.sankakucomplex.com',
    'beta.sankakucomplex.com',
    'black.sankakucomplex.com',
    'white.sankakucomplex.com',
    'sankaku.app',
    'www.sankaku.app',
}
CANONICAL = 'https://www.sankakucomplex.com/posts/{}'

MD5_RE = re.compile(r'^[0-9a-fA-F]{32}$')
# /post/show/<id>, /posts/<id>, optionally behind a language prefix like /en
POST_PATH_RE = re.compile(r'^(?:/[a-z]{2}(?:[-_][A-Z]{2})?)?/posts?(?:/show)?/(\w+)/?$')


def extract_post_id(url: str) -> str | None:
    """Returns the ID segment of a Sankaku post URL, or None for any other URL."""

    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ('http', 'https') or parts.netloc.lower() not in HOSTS:
        return None

    match = POST_PATH_RE.match(parts.path)
    return match[1] if match else None


def fix_source(source: str, post_md5: str | None, resolve_md5: Callable[[str], str | None]) -> tuple[str, int]:
    """
    Rewrites all Sankaku post URLs in a szurubooru source field to their canonical form.

    Sankaku dropped numeric post IDs: chan URLs carry the file's md5 hash, www URLs the
    new alphanumeric post ID. URLs with an md5 hash are resolved through the Sankaku API,
    legacy numeric IDs through the szurubooru file checksum (which matches Sankaku's md5
    if the file was imported unmodified). URLs that cannot be resolved are kept as-is.

    Args:
        source (str): The newline-separated source field of a szurubooru post.
        post_md5 (str | None): The md5 checksum of the szurubooru post's file.
        resolve_md5 (Callable): Returns the Sankaku post ID for an md5 hash, or None.

    Returns:
        tuple[str, int]: The rewritten source field and the number of unresolvable URLs.
    """

    lines = []
    unresolved = 0

    for line in source.splitlines():
        url = line.strip()
        post_id = extract_post_id(url) if url else None

        if post_id:
            if MD5_RE.match(post_id):
                new_id = resolve_md5(post_id.lower())
            elif post_id.isdigit():
                # Legacy numeric ID: only the file checksum can still identify the post
                new_id = resolve_md5(post_md5.lower()) if post_md5 else None
            else:
                new_id = post_id

            if new_id:
                line = CANONICAL.format(new_id)
            else:
                unresolved += 1

        lines.append(line)

    # Rewriting can produce duplicate lines; drop them while preserving order
    seen = set()
    lines = [line for line in lines if not (line in seen or seen.add(line))]

    return '\n'.join(lines), unresolved


@logger.catch
def main(query: str = 'source:*sankaku*', dry_run: bool = False) -> None:
    """
    Rewrites outdated Sankaku source URLs of szurubooru posts to their canonical form.

    Args:
        query (str): The query to use for retrieving posts.
        dry_run (bool, optional): Only log what would change without updating posts.

    Returns:
        None
    """

    # Clients only exist after setup_clients(), so they can't be imported at module level
    from szurubooru_toolkit import sankaku
    from szurubooru_toolkit import szuru

    try:
        hide_progress = config.globals.get('hide_progress', False)

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Start fixing Sankaku sources...')

        cache = {}

        def resolve_md5(md5: str) -> str | None:
            if md5 not in cache:
                try:
                    results = sankaku.search(f'md5:{md5}', limit=1)
                except httpx.HTTPError as e:
                    # Not cached, so a later post with the same md5 tries again
                    logger.warning(f'Could not search Sankaku for md5 {md5}: {e}')
                    return None
                cache[md5] = results[0]['id'] if results else None
            return cache[md5]

        updated = unresolved_posts = 0

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
            new_source, unresolved = fix_source(post.source, post.md5, resolve_md5)

            if unresolved:
                unresolved_posts += 1
                logger.warning(f'Could not resolve {unresolved} Sankaku URL(s) of post {post.id}')

            if new_source != post.source:
                updated += 1
                if dry_run:
                    logger.info(f'Would update post {post.id}: {post.source!r} -> {new_source!r}')
                else:
                    post.source = new_source
                    szuru.update_post(post)

        action = 'Would update' if dry_run else 'Updated'
        logger.success(f'Finished! {action} {updated} post(s), {unresolved_posts} post(s) with unresolvable URLs.')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        interrupt_exit()


if __name__ == '__main__':
    main()
