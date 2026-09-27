"""Preserve source categories and create only missing, classified tags."""

import threading

from szurubooru_toolkit.szurubooru import TagExistsError
from szurubooru_toolkit.szurubooru import TagNotFoundError


CATEGORY_NAMES = {0: 'general', 1: 'artist', 3: 'copyright', 4: 'character', 5: 'meta'}
# Sankaku numbers its tag types differently: 5 is genre, 8 medium, 9 meta (studio 2 has no equivalent)
SANKAKU_CATEGORY_NAMES = {0: 'general', 1: 'artist', 3: 'copyright', 4: 'character', 5: 'general', 8: 'meta', 9: 'meta'}
# gallery-dl writes Sankaku's extra types as tags_genre and tags_medium
_KEY_CATEGORIES = {category: category for category in CATEGORY_NAMES.values()} | {'genre': 'general', 'medium': 'meta'}
_lock = threading.Lock()


def extract_categories(metadata: dict) -> dict[str, str]:
    """Read categorized strings from booru metadata, or typed Sankaku tags."""
    result = {}
    for key_name, category in _KEY_CATEGORIES.items():
        for key in (f'tag_string_{key_name}', f'tags_{key_name}'):
            tags = metadata.get(key, [])
            if isinstance(tags, str):
                tags = tags.split()
            if isinstance(tags, list):
                result.update({tag: category for tag in tags if isinstance(tag, str)})
    tags = metadata.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                name = tag.get('tagName') or tag.get('name')
                category = tag.get('type', tag.get('category'))
                if isinstance(category, str) and category.isdigit():
                    category = int(category)
                category = SANKAKU_CATEGORY_NAMES.get(category, category)
                if name and category in CATEGORY_NAMES.values():
                    result[name] = category
    return result


def ensure_tag_categories(client, config, tags, categories, *, dry_run=False):
    """Create classified tags before post writes; leave existing tags untouched.

    The per-client cache and lock avoid repeated writes across upload workers.
    Unknown categories are left to the server's default when it saves the post.
    """
    options = config.tag_categories
    if dry_run or not options['enabled']:
        return
    hints = {name.replace(' ', '_'): category for name, category in categories.items()}
    with _lock:
        known = getattr(client, '_categorized_tags', None)
        if known is None:
            known = client._categorized_tags = set()
        missing = []
        for name in sorted({tag.replace(' ', '_') for tag in tags} - known):
            try:
                client.get_tag(name)
            except TagNotFoundError:
                missing.append(name)
            else:
                known.add(name)
        if options['lookup_danbooru']:
            from szurubooru_toolkit import danbooru

            unknown = [name for name in missing if name not in hints]
            if unknown:
                for name, category in danbooru.get_tag_categories(unknown).items():
                    if category in CATEGORY_NAMES:
                        hints[name] = CATEGORY_NAMES[category]
        for name in missing:
            target = options['category_map'].get(hints.get(name))
            if not target:
                continue
            try:
                client.create_tag(name, target)
            except TagExistsError:
                pass  # Another process created it; never overwrite its category.
            known.add(name)
