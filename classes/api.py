import json
import requests
import urllib
import os
from math import ceil
from .post import Post
from misc.helpers import resize_image

class API:
    def __init__(self, szuru_address, szuru_api_token, szuru_public):
        self.szuru_address   = szuru_address
        self.szuru_public    = szuru_public
        self.szuru_api_url   = self.szuru_address + '/api'
        self.szuru_api_token = szuru_api_token
        self.headers         = {'Accept':'application/json', 'Authorization':'Token ' + szuru_api_token}

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
            query_url     = self.szuru_api_url + '/posts/?query=' + query
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
                        query_url = self.szuru_api_url + '/posts/?offset=' + str(page) + '00&query=' + query
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
        Returns a boilerplate post object with post_id, image_url, version and already set tags.

        Args:
            post_id: The id from the post

        Returns:
            post: A post object

        Raises:
            Exception
        """

        try:
            query_url   = self.szuru_api_url + '/post/' + post_id
            response    = requests.get(query_url, headers=self.headers)

            content_url = response.json()['contentUrl']
            image_url   = self.szuru_address + '/' + content_url
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

        query_url = self.szuru_api_url + '/post/' + post.id
        meta_data = json.dumps({"version": post.version, "tags": post.tags, "source": post.source, "safety": post.rating})

        try:
            response = requests.put(query_url, headers=self.headers, data=meta_data)
            if 'description' in response.json():
                raise Exception(response.json()['description'])
        except Exception as e:
            print(f'Could not edit your post: {e}')

    def create_tags(self):
        """
        Create or update existing tags with the supplied tags

        Args:
            post: A post object

        Raises:
            Exception
        """

        with open("./misc/tags/tags.txt") as tags_stream:
            for _, tag in enumerate(tags_stream):
                tag = tag.split(',')
                tag[1] = tag[-1].strip()

                if tag[1] == '0':
                    tag[1] = 'default'
                elif tag[1] == '1':
                    tag[1] = 'artist'
                elif tag[1] == '3':
                    tag[1] = 'series'
                elif tag[1] == '4':
                    tag[1] = 'character'
                elif tag[1] == '5':
                    tag[1] = 'meta'
                    
                try:
                    query_url = self.szuru_api_url + '/tags'
                    meta_data = json.dumps({"names": tag[0], "category": tag[1]})
                    response = requests.post(query_url, headers=self.headers, data=meta_data)

                    if not response.json()['description'] == None:
                        raise Exception(response.json()['description'])
                    else:
                        print(f'Created tag {tag[0]} with category {tag[1]}')
                except Exception as e:
                    try:
                        query_url = self.szuru_api_url + '/tag/' + tag[0]
                        response_tag = requests.get(query_url, headers=self.headers)

                        if not response_tag.json()['category'] == tag[1]:
                            meta_data = json.dumps({
                                "version": response_tag.json()['version'],
                                "names": tag[0],
                                "category": tag[1]})
                            print(meta_data)
                            response = requests.put(query_url, headers=self.headers, data=meta_data)
                            print()
                            print(response.json())
                            if not response.json()['description'] == None:
                                raise Exception(response.json()['description'])
                    except Exception as e:
                        print(f'Could not update tag: {e}')
