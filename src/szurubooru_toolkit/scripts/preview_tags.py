from __future__ import annotations

from pathlib import Path

import numpy as np
from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.wdtagger import CATEGORY_CHARACTER
from szurubooru_toolkit.wdtagger import CATEGORY_GENERAL
from szurubooru_toolkit.wdtagger import CATEGORY_RATING
from szurubooru_toolkit.wdtagger import RATING_MAP
from szurubooru_toolkit.wdtagger import WDTagger


# Video file extensions handled via frame sampling instead of direct image decoding
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mkv', '.avi', '.mov'}


def format_scores(
    tags: np.ndarray,
    categories: np.ndarray,
    results: np.ndarray,
    threshold: float,
    character_threshold: float,
    review_threshold: float | None,
    min_score: float,
) -> str:
    """
    Formats raw WD tagger scores as a human readable threshold report.

    Every tag scoring at least `min_score` is listed under its category, marked with
    whether it clears its threshold (✓), falls into the character review band (~) or
    gets dropped (✗).

    Args:
        tags (np.ndarray): The tag names, aligned with `results`.
        categories (np.ndarray): The tag categories, aligned with `results`.
        results (np.ndarray): The per-tag confidence scores.
        threshold (float): The general tag threshold.
        character_threshold (float): The character tag threshold.
        review_threshold (float | None): The lower bound of the review band, or None if disabled.
        min_score (float): Scores below this are omitted from the report.

    Returns:
        str: The formatted report.
    """

    lines = []

    rating_indices = np.where(categories == CATEGORY_RATING)[0]
    if len(rating_indices) > 0:
        winner = rating_indices[np.argmax(results[rating_indices])]
        rating_parts = []
        for index in rating_indices:
            marker = '*' if index == winner else ' '
            rating_parts.append(f'{tags[index]} {results[index]:.2f}{marker}')
        lines.append(f'Rating: {"  ".join(rating_parts)} -> {RATING_MAP.get(str(tags[winner]), "?")}')

    def section(title: str, category: int, cutoff: float, review: float | None) -> None:
        indices = np.where((categories == category) & (results >= min_score))[0]
        indices = indices[np.argsort(results[indices])[::-1]]

        lines.append('')
        lines.append(title)

        if len(indices) == 0:
            lines.append(f'  (no scores above {min_score})')
            return

        for index in indices:
            score = results[index]
            if score > cutoff:
                marker = '✓'  # included
            elif review is not None and score > review:
                marker = '~'  # review band
            else:
                marker = '✗'  # excluded
            lines.append(f'  {marker} {tags[index]:<40} {score:.3f}')

    review_note = f', review band > {review_threshold}' if review_threshold is not None else ''
    section(f'General tags (threshold > {threshold}):', CATEGORY_GENERAL, threshold, None)
    section(f'Characters (threshold > {character_threshold}{review_note}):', CATEGORY_CHARACTER, character_threshold, review_threshold)

    return '\n'.join(lines)


@logger.catch
def main(target: str) -> None:
    """
    Shows all WD tagger scores near the thresholds for a local file or szurubooru post.

    Args:
        target (str): A path to a local media file, or a szurubooru post id.

    Returns:
        None
    """

    path = Path(target)

    if path.is_file():
        media = path.read_bytes()
        is_video = path.suffix.lower() in VIDEO_EXTENSIONS
        source = str(path)
    elif target.isnumeric():
        post = szuru.get_post(target)
        media = download_media(post.content_url, post.md5)
        is_video = post.type == 'video'
        source = f'post {post.id}'
    else:
        logger.critical(f'"{target}" is neither an existing file nor a post id.')
        exit(1)

    tagger = WDTagger(config.auto_tagger['wd_tagger_model'], config.auto_tagger['wd_tagger_providers'])

    results = tagger.predict_video(media) if is_video else tagger.predict(media)

    if results is None:
        logger.critical(f'Could not tag {source}.')
        exit(1)

    review_threshold = config.auto_tagger['wd_tagger_review_threshold'] if config.auto_tagger['wd_tagger_review'] else None

    report = format_scores(
        tagger.tags,
        tagger.categories,
        results,
        threshold=config.auto_tagger['wd_tagger_threshold'],
        character_threshold=config.auto_tagger['wd_tagger_character_threshold'],
        review_threshold=review_threshold,
        min_score=config.preview_tags['min_score'],
    )

    print(f'WD tagger scores for {source} (model: {config.auto_tagger["wd_tagger_model"]})')
    print(report)


if __name__ == '__main__':
    main()
