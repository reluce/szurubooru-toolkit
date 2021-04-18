from pybooru import Danbooru as Danbooru_Module

class Danbooru:
    def __init__(self, danbooru_user, danbooru_api_key):
        self.client = Danbooru_Module(
            'danbooru',
            username = danbooru_user,
            api_key  = danbooru_api_key
        )

    def get_result(self, result_url):
        post_id = result_url.split('/')[-1]
        self.result = self.client.post_show(post_id)

    def get_tags(self):
        return(self.result['tag_string'].split())

    def get_rating(self):
        return(self.result['rating'])
