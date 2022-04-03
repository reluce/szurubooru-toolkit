import os
import urllib
from pathlib import Path
from time import sleep

from szurubooru_toolkit.utils import convert_rating


os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np  # noqa E402
import PIL  # noqa E402
import tensorflow as tf  # noqa E402
from loguru import logger  # noqa E402


class Deepbooru:
    def __init__(self, model_path):
        self.model = self.load_model(model_path)

    def load_model(self, model_path):
        try:
            self.model = tf.keras.models.load_model(model_path, compile=False)
        except Exception as e:
            logger.debug(e)
            logger.critical('Model could not be read. Download it from https://github.com/KichangKim/DeepDanbooru')
            exit()

        with open('./misc/deepbooru/tags.txt') as tags_stream:
            self.tags = np.array([tag for tag in (tag.strip() for tag in tags_stream) if tag])

        return self.model

    def tag_image(self, local_temp_path: str, image_url: str, threshold: float = 0.6):
        filename = image_url.split('/')[-1]

        for i in range(1, 12):
            try:
                local_file_path = urllib.request.urlretrieve(image_url, Path(local_temp_path) / filename)[0]
                break
            except urllib.error.URLError:
                logger.warning('Could not establish connection to szurubooru, trying again in 5s...')
                sleep(5)

        try:
            image = np.array(PIL.Image.open(local_file_path).convert('RGB').resize((512, 512))) / 255.0
        except OSError as e:
            logger.warning(e, 'Image URL: ', image_url)
            return [], 'unsafe'  # Keep script running

        results = self.model.predict(np.array([image])).reshape(self.tags.shape[0])
        result_tags = {}
        for i in range(len(self.tags)):
            if results[i] > float(threshold):
                result_tags[self.tags[i]] = results[i]

        tags = list(result_tags.keys())
        logger.debug(f'Guessed following tags: {tags}')

        rating = 'unsafe'

        if not tags:
            logger.warning(f'Deepbooru could not guess tags for image {image_url}')
        else:
            try:
                rating = convert_rating(tags[-1])
                logger.debug(f'Guessed rating {rating}')
                del tags[-1]
            except IndexError:
                logger.warning(f'Could not guess rating for image {image_url}. Defaulting to unsafe.')

            # Optional: add deepbooru tag. We can always reference source:Deepbooru though.
            # tags.append('deepbooru')

        if rating is None:
            rating = 'unsafe'

        # Remove temporary image
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

        return tags, rating
