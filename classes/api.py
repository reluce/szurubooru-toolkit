import json
import requests
import urllib
import os
from math import ceil
from .post import Post
from misc.helpers import resize_image

class API:
    def __init__(self, booru_address, booru_api_token, booru_offline):
        self.booru_address   = booru_address
        self.booru_offline   = booru_offline
        self.booru_api_url   = self.booru_address + '/api'
        self.booru_api_token = booru_api_token
        self.headers     = {'Accept':'application/json', 'Authorization':'Token ' + booru_api_token}

    def get_post_ids(self, query):
        """
        Return the found post ids of the supplied query.

        Args:
            query: The user input query

        Returns:
            post_ids: A list of the found post ids
            total: The total amount of posts found

        Raises:
            Exception
        """

        if query.isnumeric():
            query = 'id:' + query

        try:
            query_url     = self.booru_api_url + '/posts/?query=' + query
            response      = requests.get(query_url, headers=self.headers)

            total         = str(response.json()['total'])
            posts         = response.json()['results']
            pages         = ceil(int(total) / 100)
            post_ids      = []

            if posts:
                print(f"Found {total} posts. Start tagging..." )

                for post in posts:
                    post_ids.append(str(post['id']))

                if pages > 1:
                    for page in range(1, pages + 1):
                        query_url = self.booru_api_url + '/posts/?offset=' + str(page) + '00&query=' + query
                        posts     = requests.get(query_url, headers=self.headers).json()['results']

                        for post in posts:
                            post_ids.append(str(post['id']))

                return post_ids, total
            else:
                print('No posts were found for your query!')
                return 0, 0

        except Exception as e:
            print(f'Could not process your query: {e}.')

    def get_post(self, post_id, local_temp_path=None, sankaku_url=None):
        """
        Returns a boilerplate post object with post_id, image_url and version.

        Args:
            post_id: The id from the post

        Returns:
            post: A post object

        Raises:
            Exception
        """

        try:
            blacklist_extensions = ['mp4', 'webm', 'mkv']
            query_url   = self.booru_api_url + '/post/' + post_id
            response    = requests.get(query_url, headers=self.headers)

            content_url = response.json()['contentUrl']
            image_url   = self.booru_address + '/' + content_url
            md5sum      = response.json()['checksumMD5']
            version     = response.json()['version']
            tags        = response.json()['tags']
            tag_list    = []

            for tag in tags:
                tag_list.append(tag['names'][0])

            # Download image and add it to the post object
            # ToDo: Don't do that if the booru is accessible over the internet
            if not any(extension in content_url for extension in blacklist_extensions):
                filename = content_url.split('/')[-1]
                local_file_path = urllib.request.urlretrieve(image_url, local_temp_path + filename)[0]

                # Resize image if it's too big. IQDB limit is 8192KB or 7500x7500px.
                # Resize images bigger than 3MB to reduce stress on iqdb.
                image_size = os.path.getsize(local_file_path)

                if image_size > 3000000:
                    resize_image(local_file_path)

                with open(local_file_path, 'rb') as f:
                    image = f.read()

                # Remove temporary image
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
            else:
                image = None

            post = Post(md5sum, post_id, image_url, image, version, tag_list)

            return post
        except Exception as e:
            print(f'Could not get image url: {e}')

    def set_meta_data(self, post):
        """
        Set tags on post if any were found. Default source to anonymous and rating to unsafe.

        Args:
            post: A post object
        
        Raises:
            Exception
        """

        query_url = self.booru_api_url + '/post/' + post.id
        meta_data = json.dumps({"version": post.version, "tags": post.tags, "source": post.source, "safety": post.rating})

        try:
            response = requests.put(query_url, headers=self.headers, data=meta_data)
            if 'description' in response.json():
                raise Exception(response.json()['description'])
        except Exception as e:
            print(f'Could not upload your post: {e}')
        
