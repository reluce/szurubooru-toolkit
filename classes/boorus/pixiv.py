from pixivapi import Client

class Pixiv:
    def __init__(self, pixiv_user, pixiv_pass, refresh_token):
        self.client = Client()

        if refresh_token != "None":
            self.client.authenticate(refresh_token)
        else:
            self.client.login(pixiv_user, pixiv_pass)
            self.refresh_token = self.client.refresh_token
            print(f'Login to pixiv successful. Save your refresh token to your config file: {self.refresh_token}')
            print(f'You can remove the login information to pixiv afterwards.')

    def get_result(self, result_url):
        post_id = result_url.split('=')[-1]
        print(post_id)
        self.result = self.client.fetch_illustration(post_id)

    def get_tags(self):
        return(self.result['tags'])

    def get_rating(self):
        return(self.result['restrict'])
