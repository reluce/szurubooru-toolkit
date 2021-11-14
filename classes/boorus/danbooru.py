import pybooru
from pybooru import Danbooru as Danbooru_Module

class Danbooru:
    def __init__(self, danbooru_user, danbooru_api_key):
        if not danbooru_api_key == 'None':
            self.client = Danbooru_Module(
                'danbooru',
                username = danbooru_user,
                api_key  = danbooru_api_key
            )
        else:
            self.client = Danbooru_Module('danbooru')

    def get_by_md5(self, md5sum):
        try:
            self.result = self.client.post_list(md5=md5sum)
            self.source = self.result['source']
        except pybooru.exceptions.PybooruHTTPError:
            self.result = None

        return(self.result)

    def get_result(self, result_url):
        post_id = result_url.split('/')[-1]
        return self.client.post_show(post_id)

    def get_tags(self, result):
        return(result['tag_string'].split())

    def get_rating(self, result):
        return(result['rating'])
