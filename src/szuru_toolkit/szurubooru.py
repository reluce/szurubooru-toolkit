from szuru_toolkit import Config

import pyszuru


class Szurubooru:
    """Placeholder"""

    def __init__(self, szuru_url: str, szuru_user: str, szuru_token: str) -> None:
        """Placeholder"""

        self.api = pyszuru.API(base_url=szuru_url, username=szuru_user, token=szuru_token)


myconfig = Config()

szuru = Szurubooru(myconfig.szurubooru['url'], myconfig.szurubooru['username'], myconfig.szurubooru['api_token'])

posts = szuru.api.search_post('asaka_karin', show_progress_bar=True)
for post in posts:
    for tag in post.tags:
        print(tag.category)
    break

print('foo')
