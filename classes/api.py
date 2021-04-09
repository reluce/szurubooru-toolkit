import json
import requests
from math import ceil
from .post import Post

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

    def get_post(self, post_id):
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
            query_url   = self.booru_api_url + '/post/' + post_id
            response    = requests.get(query_url, headers=self.headers)

            content_url = response.json()['contentUrl']
            image_url   = self.booru_address + '/' + content_url
            version     = response.json()['version']
            tags        = response.json()['tags']
            tag_list    = []

            for tag in tags:
                tag_list.append(tag['names'][0])

            post = Post(post_id, image_url, version, tag_list)

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
            requests.put(query_url, headers=self.headers, data=meta_data)
        except Exception as e:
            print(f'Could not upload your post: {e}')
        
