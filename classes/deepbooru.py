import sys
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
import urllib
import tensorflow as tf
import numpy as np
import PIL
from misc.helpers import convert_rating

class DeepBooru():
    def __init__(self, model_path):
        self.model = self.load_model(model_path)

    def load_model(self, model_path):
        try:
            self.model = tf.keras.models.load_model(model_path, compile=False)
        except Exception as e:
            print(e)
            print('Model not found. Download it from https://github.com/KichangKim/DeepDanbooru')
            sys.exit()

        with open("./misc/deepbooru/tags.txt", 'r') as tags_stream:
            self.tags = np.array([tag for tag in (tag.strip() for tag in tags_stream) if tag])

        return self.model

    def tag_image(self, local_temp_path, image_url, threshold=0.6):
        filename = image_url.split('/')[-1]
        local_file_path = urllib.request.urlretrieve(image_url, local_temp_path + filename)[0]

        try:
            image = np.array(PIL.Image.open(local_file_path).convert('RGB').resize((512, 512))) / 255.0
        except IOError:
            return 'fail', []

        results = self.model.predict(np.array([image])).reshape(self.tags.shape[0])
        result_tags = {}
        for i in range(len(self.tags)):
            if results[i] > float(threshold):
                result_tags[self.tags[i]] = results[i]

        # Remove temporary image
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

        tags   = list(result_tags.keys())
        rating = 'unsafe'

        if not len(tags):
            print()
            print(f'DeepBooru could not guess tags for image {image_url}')
        else:
            try:
                rating = convert_rating(tags[-1])
                del tags[-1]
            except IndexError:
                print()
                print(f'Could not guess rating for image {image_url}. Defaulting to unsafe.')

            tags.append('deepbooru')

        return rating, tags
