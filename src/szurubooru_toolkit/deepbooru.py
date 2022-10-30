import os
import re
from io import BytesIO

from PIL import Image

from szurubooru_toolkit.utils import convert_rating


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np  # noqa E402
import tensorflow as tf  # noqa E402
from loguru import logger  # noqa E402
from tensorflow.python.ops.numpy_ops import np_config  # noqa E402


class Deepbooru:
    """Handles everything related to guessing tags based on machine learning."""

    def __init__(self, model_path: str) -> None:
        """Initializes a Deepbooru object and loads the `model_path`.

        Args:
            model_path (str): The local path to the DeepDanbooru model.
        """

        self.load_model(model_path)
        np_config.enable_numpy_behavior()

    def load_model(self, model_path: str) -> None:
        """Loads the DeepDanbooru model.

        Args:
            model_path (str): _description_
        """

        try:
            self.model = tf.keras.models.load_model(model_path, compile=False)
        except Exception as e:
            logger.debug(e)
            print('')
            logger.critical('Model could not be read. Download it from https://github.com/KichangKim/DeepDanbooru')
            exit()

        with open('./misc/deepbooru/tags.txt') as tags_stream:
            self.tags = np.array([tag for tag in (tag.strip() for tag in tags_stream) if tag])

    def tag_image(self, image: bytes, threshold: float = 0.6, set_tag: bool = True) -> tuple[list, str]:
        """Guesses the tags and rating of the provided image from `image_path`.

        Args:
            image (bytes): The image in bytes which tags and rating should be guessed.
            threshhold (float): The accuracy threshold of the guessed tags, 1 being 100%. Defaults to `0.6`.
            set_tag (bool): Add tag "deepbooru"

        Returns:
            tuple[list, str]: A tuple with the guessed tags as a `list` and the rating as a `str`.
        """

        try:
            with Image.open(BytesIO(image)) as opened_image:
                image = np.array(opened_image.convert('RGB').resize((512, 512))) / 255.0
        except Exception:
            print('')
            logger.warning('Failed to convert image to Deepbooru format')
            return

        results = self.model(np.array([image])).reshape(self.tags.shape[0])

        result_tags = {}
        for i in range(len(self.tags)):
            if results[i] > float(threshold):
                result_tags[self.tags[i]] = results[i]

        tags = list(result_tags.keys())
        logger.debug(f'Guessed following tags: {tags}')

        rating = 'unsafe'

        if not tags:
            print('')
            logger.warning('Deepbooru could not guess tags for image!')
        else:
            try:
                rating = convert_rating(tags[-1])
                logger.debug(f'Guessed rating {rating}')
                del tags[-1]
            except IndexError:
                print('')
                logger.warning('Could not guess rating for image! Defaulting to unsafe.')

            if set_tag:
                tags.append('deepbooru')

        if rating is None:
            rating = 'unsafe'

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
