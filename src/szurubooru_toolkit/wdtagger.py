import csv
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime
from loguru import logger
from PIL import Image

from szurubooru_toolkit.utils import resolve_onnx_providers


# Category ids in selected_tags.csv
CATEGORY_GENERAL = 0
CATEGORY_CHARACTER = 4
CATEGORY_RATING = 9

# WD taggers rate with the current Danbooru rating scheme (general/sensitive/questionable/explicit),
# szurubooru only knows safe/sketchy/unsafe.
RATING_MAP = {
    'general': 'safe',
    'sensitive': 'sketchy',
    'questionable': 'sketchy',
    'explicit': 'unsafe',
}

# Marker tag for posts whose character prediction landed in the review band
REVIEW_TAG = 'needs_review'

# Videos get one sampled frame per this many seconds, clamped to the min/max below
VIDEO_SECONDS_PER_FRAME = 15
VIDEO_MIN_FRAMES = 3
VIDEO_MAX_FRAMES = 16


def frame_timestamps(duration: float, seconds_per_frame: int = VIDEO_SECONDS_PER_FRAME) -> list[float]:
    """
    Returns the timestamps at which to sample frames from a video.

    Longer videos get more frames (one per `seconds_per_frame`, clamped to
    [VIDEO_MIN_FRAMES, VIDEO_MAX_FRAMES]), spread evenly across 5%-95% of the
    duration so intros and credits don't dominate the samples.

    Args:
        duration (float): The video duration in seconds.
        seconds_per_frame (int, optional): Target seconds of video per sampled frame.

    Returns:
        list[float]: The timestamps in seconds, ascending.
    """

    if duration <= 0:
        return [0.0]

    count = max(VIDEO_MIN_FRAMES, min(VIDEO_MAX_FRAMES, round(duration / seconds_per_frame)))

    start = duration * 0.05
    end = duration * 0.95

    if count == 1:
        return [duration / 2]

    step = (end - start) / (count - 1)

    return [start + index * step for index in range(count)]


class WDTagger:
    """Tags images with one of SmilingWolf's WD taggers (https://huggingface.co/SmilingWolf) via ONNX Runtime."""

    def __init__(self, model: str, providers: list[str] = None) -> None:
        """
        Initializes a WDTagger object and loads the WD tagger model.

        Args:
            model (str): Either a Hugging Face repo id (e.g. "SmilingWolf/wd-eva02-large-tagger-v3") whose files get
                downloaded to the local Hugging Face cache on first use, or a local directory containing model.onnx
                and selected_tags.csv.
            providers (list[str], optional): ONNX Runtime execution providers to use, in order
                of preference (e.g. ['CoreMLExecutionProvider'] on Apple Silicon or
                ['CUDAExecutionProvider'] on NVIDIA GPUs). CPU is always kept as fallback.
                Defaults to CPU only.
        """

        self.load_model(model, providers)

    def load_model(self, model: str, providers: list[str] = None) -> None:
        """
        Loads the WD tagger ONNX model and its tag list.

        Args:
            model (str): Hugging Face repo id or local directory.
            providers (list[str], optional): ONNX Runtime execution providers. Defaults to CPU only.
        """

        model_dir = Path(model)
        if model_dir.is_dir():
            model_path = model_dir / 'model.onnx'
            tags_path = model_dir / 'selected_tags.csv'
        else:
            try:
                from huggingface_hub import hf_hub_download
            except ImportError:
                logger.critical(
                    'Downloading WD tagger models requires the "wd-tagger" extra. Install it with:'
                    ' pip install szurubooru-toolkit[wd-tagger].'
                    ' Alternatively, set wd_tagger_model to a local directory containing model.onnx and selected_tags.csv.',
                )
                exit(1)

            try:
                logger.debug(f'Downloading WD tagger model "{model}" from Hugging Face (cached after first download)...')
                model_path = hf_hub_download(repo_id=model, filename='model.onnx')
                tags_path = hf_hub_download(repo_id=model, filename='selected_tags.csv')
            except Exception as e:
                logger.debug(f'Model download error: {e}')
                logger.critical(f'WD tagger model "{model}" could not be downloaded. Check your wd_tagger_model setting.')
                exit(1)

        resolved_providers = resolve_onnx_providers(providers)

        try:
            # Inference session; session.run is thread-safe, so concurrent
            # tagging workers can share it without a lock.
            self.session = onnxruntime.InferenceSession(str(model_path), providers=resolved_providers)
            logger.debug(f'WD tagger model loaded from {model_path} with providers {self.session.get_providers()}')
        except Exception as e:
            logger.debug(f'Model loading error: {e}')
            logger.critical(f'WD tagger model "{model}" could not be loaded. Check your wd_tagger_model setting.')
            exit(1)

        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        self.output_name = self.session.get_outputs()[0].name
        self.input_size = model_input.shape[1]  # Model input is (batch, height, width, 3)

        try:
            with open(tags_path, newline='', encoding='utf-8') as tags_stream:
                rows = list(csv.DictReader(tags_stream))
            self.tags = np.array([row['name'] for row in rows])
            self.categories = np.array([int(row['category']) for row in rows])
        except (FileNotFoundError, KeyError):
            logger.critical(f'selected_tags.csv not found or malformed. Place it next to the model file in {tags_path}.')
            exit(1)

    def prepare_image(self, image: Image.Image) -> np.ndarray:
        """
        Converts an image to the WD tagger input format.

        Composites transparency onto white, pads the image to a square, resizes it to the model input size and returns
        a float32 BGR array with pixel values 0-255 (the format WD taggers were trained on).

        Args:
            image (Image.Image): The image to convert.

        Returns:
            np.ndarray: The image as an array of shape (1, size, size, 3).
        """

        canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image.convert('RGBA'))
        image = canvas.convert('RGB')

        max_dim = max(image.size)
        padded = Image.new('RGB', (max_dim, max_dim), (255, 255, 255))
        padded.paste(image, ((max_dim - image.width) // 2, (max_dim - image.height) // 2))

        if max_dim != self.input_size:
            padded = padded.resize((self.input_size, self.input_size), Image.BICUBIC)

        image_array = np.asarray(padded, dtype=np.float32)[:, :, ::-1]  # RGB -> BGR

        return np.expand_dims(image_array, axis=0)

    def predict(self, image: bytes) -> np.ndarray | None:
        """
        Returns the raw per-tag confidence scores for an image.

        The scores align index-wise with `self.tags` and `self.categories`.

        Args:
            image (bytes): The image content.

        Returns:
            np.ndarray | None: The confidence scores, or None if the image could not be processed.
        """

        try:
            with Image.open(BytesIO(image)) as opened_image:
                image_array = self.prepare_image(opened_image)
        except Exception:
            logger.warning('Failed to convert image to WD tagger format')
            return None

        try:
            return self.session.run([self.output_name], {self.input_name: image_array})[0][0]
        except Exception as e:
            logger.debug(f'Prediction error: {e}')
            logger.warning('Failed to predict image with WD tagger')
            return None

    def predict_video(self, video: bytes) -> np.ndarray | None:
        """
        Returns the averaged per-tag confidence scores over frames sampled from a video.

        Frames are extracted with ffmpeg at timestamps spread across the video; longer
        videos get more frames (see `frame_timestamps`). Averaging the scores keeps tags
        that hold up across the video and suppresses single-frame flukes.

        Args:
            video (bytes): The video content.

        Returns:
            np.ndarray | None: The averaged confidence scores, or None if no frame could be processed.
        """

        ffmpeg = shutil.which('ffmpeg')
        ffprobe = shutil.which('ffprobe')

        if not ffmpeg or not ffprobe:
            logger.warning('Video tagging requires ffmpeg and ffprobe on the PATH. Skipping video...')
            return None

        with tempfile.NamedTemporaryFile(suffix='.video') as video_file:
            video_file.write(video)
            video_file.flush()

            try:
                probe = subprocess.run(
                    [ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video_file.name],
                    capture_output=True,
                    check=True,
                    timeout=60,
                )
                duration = float(probe.stdout.strip())
            except (subprocess.SubprocessError, ValueError) as e:
                logger.debug(f'ffprobe error: {e}')
                logger.warning('Could not determine video duration. Skipping video...')
                return None

            timestamps = frame_timestamps(duration)
            logger.debug(f'Sampling {len(timestamps)} frames from a {duration:.1f}s video')

            frame_scores = []
            for timestamp in timestamps:
                try:
                    frame = subprocess.run(
                        [ffmpeg, '-v', 'error', '-ss', f'{timestamp:.2f}', '-i', video_file.name]
                        + ['-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                        capture_output=True,
                        check=True,
                        timeout=120,
                    ).stdout
                except subprocess.SubprocessError as e:
                    logger.debug(f'ffmpeg error at {timestamp:.2f}s: {e}')
                    continue

                if not frame:
                    continue

                scores = self.predict(frame)
                if scores is not None:
                    frame_scores.append(scores)

        if not frame_scores:
            logger.warning('Could not extract any usable frame from video')
            return None

        return np.mean(frame_scores, axis=0)

    def scores_to_tags(
        self,
        results: np.ndarray,
        default_safety: str,
        threshold: float,
        character_threshold: float,
        set_tag: bool,
        review_threshold: float = None,
    ) -> tuple[list, str]:
        """
        Converts raw confidence scores into a tag list and rating.

        General tags and character tags use separate confidence thresholds since character predictions are usually
        either confident or wrong. The rating is picked from the most confident of the model's four rating outputs.
        With a review threshold set, character scores landing in [review_threshold, character_threshold) add the
        "needs_review" tag so ambiguous character matches can be curated manually.

        Args:
            results (np.ndarray): The per-tag confidence scores from `predict` or `predict_video`.
            default_safety (str): The safety rating to fall back to.
            threshold (float): The confidence threshold for general tags.
            character_threshold (float): The confidence threshold for character tags.
            set_tag (bool): Add tag "wd_tagger" to the post.
            review_threshold (float, optional): Lower bound of the character review band. Disabled if None.

        Returns:
            tuple[list, str]: A tuple with the guessed tags as a `list` and the rating as a `str`.
        """

        character_categories = self.categories == CATEGORY_CHARACTER
        general = (self.categories == CATEGORY_GENERAL) & (results > float(threshold))
        characters = character_categories & (results > float(character_threshold))
        tags = self.tags[general | characters].tolist()

        rating_indices = np.where(self.categories == CATEGORY_RATING)[0]
        if len(rating_indices) > 0:
            rating_tag = self.tags[rating_indices[np.argmax(results[rating_indices])]]
            rating = RATING_MAP.get(rating_tag, default_safety)
            logger.debug(f'Guessed rating {rating} (from "{rating_tag}")')
        else:
            rating = default_safety

        if not tags:
            logger.warning(
                f'WD tagger could not guess tags for image! Maximum inference was {np.amax(results)}, while threshold is {threshold}!',
            )
        else:
            logger.debug(f'Guessed following tags: {tags}')

            if set_tag:
                tags.append('wd_tagger')

        if review_threshold is not None:
            review = character_categories & (results > float(review_threshold)) & (results <= float(character_threshold))
            near_misses = {tag: results[index] for index, tag in enumerate(self.tags) if review[index]}

            if near_misses:
                formatted = ', '.join(f'{tag} ({score:.2f})' for tag, score in near_misses.items())
                logger.debug(f'Character scores in review band: {formatted}')
                tags.append(REVIEW_TAG)

        return tags, rating

    def tag_image(
        self,
        image: bytes,
        default_safety: str,
        threshold: float = 0.35,
        character_threshold: float = 0.75,
        set_tag: bool = True,
        review_threshold: float = None,
    ) -> tuple[list, str]:
        """
        Guesses the tags and rating of the provided image.

        Args:
            image (bytes): The image in bytes which tags and rating should be guessed.
            default_safety (str): The safety rating to fall back to if the image cannot be processed.
            threshold (float): The confidence threshold for general tags, 1 being 100%. Defaults to `0.35`.
            character_threshold (float): The confidence threshold for character tags. Defaults to `0.75`.
            set_tag (bool): Add tag "wd_tagger" to the post.
            review_threshold (float, optional): Lower bound of the character review band. Disabled if None.

        Returns:
            tuple[list, str]: A tuple with the guessed tags as a `list` and the rating as a `str`.
        """

        results = self.predict(image)

        if results is None:
            return [], default_safety

        return self.scores_to_tags(results, default_safety, threshold, character_threshold, set_tag, review_threshold)

    def tag_video(
        self,
        video: bytes,
        default_safety: str,
        threshold: float = 0.35,
        character_threshold: float = 0.75,
        set_tag: bool = True,
        review_threshold: float = None,
    ) -> tuple[list, str]:
        """
        Guesses the tags and rating of the provided video from frames sampled across its duration.

        Args:
            video (bytes): The video content which tags and rating should be guessed.
            default_safety (str): The safety rating to fall back to if the video cannot be processed.
            threshold (float): The confidence threshold for general tags, 1 being 100%. Defaults to `0.35`.
            character_threshold (float): The confidence threshold for character tags. Defaults to `0.75`.
            set_tag (bool): Add tag "wd_tagger" to the post.
            review_threshold (float, optional): Lower bound of the character review band. Disabled if None.

        Returns:
            tuple[list, str]: A tuple with the guessed tags as a `list` and the rating as a `str`.
        """

        results = self.predict_video(video)

        if results is None:
            return [], default_safety

        return self.scores_to_tags(results, default_safety, threshold, character_threshold, set_tag, review_threshold)
