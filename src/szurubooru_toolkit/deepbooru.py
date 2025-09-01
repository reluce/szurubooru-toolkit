import os
import re
from io import BytesIO

from PIL import Image

from szurubooru_toolkit.utils import convert_rating


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np  # noqa E402
import tensorflow as tf  # noqa E402
import warnings  # noqa E402
from loguru import logger  # noqa E402
from tensorflow.python.ops.numpy_ops import np_config  # noqa E402

# Suppress specific Keras warnings about input structure
warnings.filterwarnings('ignore', message='The structure of `inputs` doesn\'t match the expected structure.*')

# Optimize TensorFlow for Apple Silicon
if len(tf.config.list_physical_devices('GPU')) > 0:
    # Enable memory growth to avoid allocating all GPU memory at once
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
        except RuntimeError as e:
            logger.debug(f"GPU memory growth setting failed: {e}")
    
    logger.debug("TensorFlow Metal GPU acceleration enabled for Apple Silicon")


class Deepbooru:
    """Handles everything related to guessing tags based on machine learning."""

    def __init__(self, model_path: str) -> None:
        """
        Initializes a Deepbooru object and loads the DeepDanbooru model.

        This method initializes a Deepbooru object and loads the DeepDanbooru model from the provided path. It also enables
        numpy behavior for TensorFlow.

        Args:
            model_path (str): The local path to the DeepDanbooru model.
        """

        self.load_model(model_path)
        np_config.enable_numpy_behavior()

    def load_model(self, model_path: str) -> None:
        """
        Loads the Deepbooru model.

        This method loads the Deepbooru model from the provided path. If the model cannot be loaded, it logs the error and
        exits the program. It also loads the tags from a text file and stores them in a numpy array.

        Args:
            model_path (str): The local path to the Deepbooru model.

        Raises:
            Exception: If the model cannot be loaded.
        """

        try:
            # Load model with additional options for better compatibility
            self.model = tf.keras.models.load_model(
                model_path, 
                compile=False,
                safe_mode=False  # Disable safe mode for older models
            )
            logger.debug(f"Model loaded successfully from {model_path}")
            
            # Log model input information for debugging
            if hasattr(self.model, 'input_names') and self.model.input_names:
                logger.debug(f"Model input names: {self.model.input_names}")
            if hasattr(self.model, 'input_shape'):
                logger.debug(f"Model input shape: {self.model.input_shape}")
                
            self.predict_fn = tf.function(
                lambda inputs: self.model(inputs, training=False),
                input_signature=[tf.TensorSpec(shape=(None, 512, 512, 3), dtype=tf.float32)],
                reduce_retracing=True,
            )

        except Exception as e:
            logger.debug(f"Model loading error: {e}")
            logger.critical('Model could not be read. Download it from https://github.com/KichangKim/DeepDanbooru')
            exit()

        try:
            deepbooru_path = os.path.dirname(model_path)
            with open(deepbooru_path + '/tags.txt') as tags_stream:
                self.tags = np.array([tag for tag in (tag.strip() for tag in tags_stream) if tag])
        except FileNotFoundError:
            logger.critical('tags.txt not found. Place it in the same directory as the Deepbooru model.')

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

        image = np.expand_dims(image, axis=0)
        image = tf.convert_to_tensor(image, dtype=tf.float32)
        results = self.predict_fn(image).numpy()[0]

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
