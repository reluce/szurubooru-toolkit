import os
import requests
import bs4
import re
import urllib
from misc.helpers import resize_image

class SauceNAO:
    pass

    def __init__(self, preferred_booru, booru_offline, local_temp_path):
        self.base_url          = 'https://saucenao.com/'
        self.base_url_download = self.base_url + 'search.php'
        self.preferred_booru   = preferred_booru
        self.booru_offline     = booru_offline
        self.local_temp_path   = local_temp_path

    def get_result(self, post):
        """
        If our booru is offline, upload the image to iqdb and return the result HTML page.
        Otherwise, let iqdb download the image from our szuru instance.

        Args:
            post: A post object
            booru_offline: If our booru is online or offline
            local_temp_path: Directory where images should be saved if booru is offline

        Returns:
            result_page: The IQDB HTML result page
        """

        regex = r"(?i)(https?:\/\/[\S]*" + self.preferred_booru + r"[\S]*[\d])"

        if(self.booru_offline == True):
            # Download temporary image
            filename = post.image_url.split('/')[-1]
            local_file_path = urllib.request.urlretrieve(post.image_url, self.local_temp_path + filename)[0]

            # Resize image if it's too big. IQDB limit is 8192KB or 7500x7500px.
            # Resize images bigger than 3MB to reduce stress on iqdb.
            image_size = os.path.getsize(local_file_path)

            if image_size > 3000000:
                resize_image(local_file_path)

            # Upload it to IQDB
            with open(local_file_path, 'rb') as f:
                img = f.read()
                
            files    = {'file': img}
            response = requests.post(self.base_url_download, files=files).text

            # Remove temporary image
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
        else:
            data = {"url": post.image_url}
            response = requests.post(self.base_url_download, data, timeout=20).text

        try:
            result_url = re.findall(regex, response)[0]
        except IndexError:
            result_url = None

        return(result_url)
