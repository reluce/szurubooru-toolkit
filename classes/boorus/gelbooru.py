from pygelbooru import Gelbooru as Gelbooru_Module

class Gelbooru:
    def __init__(self, gelbooru_user, gelbooru_api_key):
        if not gelbooru_api_key == 'None':
            self.client = Gelbooru_Module(
                gelbooru_user,
                gelbooru_api_key
            )
        else:
            self.client = Gelbooru_Module()

    async def get_result(self, result_url):
        post_id = result_url.split('=')[-1]
        return await self.client.get_post(post_id)

    def get_tags(self, result):
        return [tag for tag in result.tags if tag != ""]

    def get_rating(self, result):
        return(result.rating)
