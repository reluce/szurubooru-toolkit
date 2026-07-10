import re
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime
from loguru import logger
from PIL import Image

from szurubooru_toolkit.utils import convert_rating


class Deepbooru:
    """Handles everything related to guessing tags based on machine learning.

    Runs the DeepDanbooru model with ONNX Runtime. Keras (.h5) models get converted
    to ONNX once if tensorflow and tf2onnx are available, otherwise the conversion
    instructions are printed.
    """

    def __init__(self, model_path: str, providers: list[str] = None) -> None:
        """
        Initializes a Deepbooru object and loads the DeepDanbooru model.

        Args:
            model_path (str): The local path to the DeepDanbooru model (.onnx, or .h5 which
                gets converted to .onnx next to it).
            providers (list[str], optional): ONNX Runtime execution providers to use, in order
                of preference (e.g. ['CoreMLExecutionProvider'] on Apple Silicon or
                ['CUDAExecutionProvider'] on NVIDIA GPUs). CPU is always kept as fallback.
                Defaults to CPU only.
        """

        self.load_model(model_path, providers)

    @staticmethod
    def _resolve_providers(providers: list[str] | None) -> list[str]:
        """
        Validates the requested execution providers against the available ones.

        Unavailable providers are dropped with a warning; the CPU provider is always
        appended as fallback.
        """

        available = onnxruntime.get_available_providers()
        resolved = []

        for provider in providers or []:
            if provider == 'CPUExecutionProvider':
                continue
            if provider in available:
                resolved.append(provider)
            else:
                logger.warning(f'Requested Deepbooru provider "{provider}" is not available in this onnxruntime build.')

        resolved.append('CPUExecutionProvider')

        return resolved

    def load_model(self, model_path: str, providers: list[str] = None) -> None:
        """
        Loads the Deepbooru ONNX model and the tags file next to it.

        Args:
            model_path (str): The local path to the DeepDanbooru model.
            providers (list[str], optional): ONNX Runtime execution providers. Defaults to CPU only.
        """

        onnx_path = self._resolve_model_path(model_path)
        resolved_providers = self._resolve_providers(providers)

        try:
            # Inference session; session.run is thread-safe, so concurrent
            # tagging workers can share it without a lock.
            self.session = onnxruntime.InferenceSession(str(onnx_path), providers=resolved_providers)
            self.input_name = self.session.get_inputs()[0].name
            logger.debug(f'Model loaded successfully from {onnx_path} with providers {self.session.get_providers()}')
        except Exception as e:
            logger.debug(f'Model loading error: {e}')
            logger.critical('Model could not be read. Download it from https://github.com/KichangKim/DeepDanbooru')
            exit()

        try:
            tags_file = Path(model_path).parent / 'tags.txt'
            with open(tags_file) as tags_stream:
                self.tags = np.array([tag for tag in (tag.strip() for tag in tags_stream) if tag])
        except FileNotFoundError:
            logger.critical('tags.txt not found. Place it in the same directory as the Deepbooru model.')
            exit()

    @staticmethod
    def _resolve_model_path(model_path: str) -> Path:
        """
        Resolves the configured model path to an ONNX model.

        Keras models (.h5) are looked up as a sibling .onnx file first. If none exists,
        a one-time conversion is attempted, which requires tensorflow and tf2onnx to be
        installed (only for the conversion, not for regular use).

        Args:
            model_path (str): The configured model path (.onnx or .h5).

        Returns:
            Path: The path to the ONNX model.
        """

        path = Path(model_path)

        if path.suffix != '.h5':
            return path

        onnx_path = path.with_suffix('.onnx')

        if onnx_path.exists():
            logger.debug(f'Using already converted ONNX model {onnx_path}')
            return onnx_path

        logger.info(f'Converting Keras model {path} to ONNX (one-time operation)...')

        try:
            import tensorflow as tf
            import tf2onnx
        except ImportError:
            logger.critical(
                f'Deepbooru now runs on ONNX Runtime, but "{path}" is a Keras model and no converted'
                f' model was found at "{onnx_path}". Convert it once with:\n'
                f'  pip install tensorflow~=2.15.0 tf2onnx\n'
                f'  python -m tf2onnx.convert --keras "{path}" --output "{onnx_path}"\n'
                'Afterwards tensorflow can be uninstalled again.',
            )
            exit(1)

        try:
            model = tf.keras.models.load_model(str(path), compile=False)
            tf2onnx.convert.from_keras(
                model,
                input_signature=[tf.TensorSpec(shape=(None, 512, 512, 3), dtype=tf.float32, name='input')],
                output_path=str(onnx_path),
            )
            logger.info(f'Converted model saved to {onnx_path}')
        except Exception as e:
            logger.critical(f'Could not convert the Keras model to ONNX: {e}')
            exit(1)

        return onnx_path

    def tag_image(self, image: bytes, default_safety: str, threshold: float = 0.6, set_tag: bool = True) -> tuple[list, str]:
        """
        Guesses the tags and rating of the provided image from `image_path`.

        This method guesses the tags and rating of the provided image. It opens the image, converts it to RGB, resizes it to
        512x512, and normalizes it. Then it uses the Deepbooru model to predict the tags and rating of the image. If the
        prediction accuracy is above the provided threshold, it adds the tag to the list of guessed tags. It also guesses the
        rating of the image based on the predicted tags.

        Args:
            image (bytes): The image in bytes which tags and rating should be guessed.
            default_safety (str): The default safety rating of the image.
            threshold (float): The accuracy threshold of the guessed tags, 1 being 100%. Defaults to `0.6`.
            set_tag (bool): Add tag "deepbooru".

        Returns:
            tuple[list, str]: A tuple with the guessed tags as a `list` and the rating as a `str`.

        Raises:
            Exception: If the image cannot be opened.
        """

        try:
            with Image.open(BytesIO(image)) as opened_image:
                image = np.array(opened_image.convert('RGB').resize((512, 512))) / 255.0
        except Exception:
            logger.warning('Failed to convert image to Deepbooru format')
            return

        try:
            image = np.expand_dims(image, axis=0).astype(np.float32)
            results = self.session.run(None, {self.input_name: image})[0][0]
        except Exception:
            logger.warning('Failed to predict image with Deepbooru')
            return [], default_safety

        result_tags = {}
        for i in range(len(self.tags)):
            if results[i] > float(threshold):
                result_tags[self.tags[i]] = results[i]

        tags = list(result_tags.keys())
        if not tags:
            logger.warning(
                f'Deepbooru could not guess tags for image! Maximum inference was {np.amax(results)}, while threshold is {threshold}!',
            )
            rating = default_safety
        else:
            logger.debug(f'Guessed following tags: {tags}')
            try:
                if 'rating' not in tags[-1]:
                    logger.debug(f'Deepbooru could not guess rating for image! Falling back to {default_safety}')
                    rating = default_safety
                else:
                    rating = convert_rating(tags[-1])
                    logger.debug(f'Guessed rating {rating}')
                    del tags[-1]
            except IndexError:
                logger.debug(f'Deepbooru could not guess rating for image! Falling back to {default_safety}')

            if set_tag:
                tags.append('deepbooru')

        converted_tags = []
        unsanitized_tags = []
        for tag in tags:
            if not re.match(r'\S+$', tag):
                unsanitized_tags.append(tag)
                converted_tags.append(tag.replace(' ', '_'))
                logger.debug(f'Converted whitespaces to underscores in tag: {tag}')

        sanitized_tags = [tag for tag in tags if tag not in unsanitized_tags]
        merged_tags = sanitized_tags + converted_tags
        final_tags = [*set(merged_tags)]  # Remove duplicates

        return final_tags, rating
