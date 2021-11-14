import argparse
import configparser
import json
from distutils.util import strtobool

class UserInput:
    def __init__(self):
        self.szuru_address   = ''
        self.szuru_api_token = ''
        self.szuru_api_url   = ''
        self.szuru_public    = ''
        self.szuru_headers   = ''
        self.sankaku_url     = ''
        self.query           = ''
        self.preferred_booru = ''
        self.fallback_booru  = ''
        self.upload_dir      = ''
        self.tags            = []
        self.local_temp_path = ''
        self.use_saucenao    = True,

    def parse_input(self):
        """
        Parse the user input to the script auto_tagger.py and set the object attributes accordingly.
        """

        # Create the parser
        parser = argparse.ArgumentParser(description='This script will automagically tag your szurubooru posts based on your input query.')

        # Add the arguments
        parser.add_argument('--sankaku_url', dest='sankaku_url', help='Fetch tags from specified Sankaku URL instead of searching IQDB.')
        parser.add_argument('query', help='Specify a single post id to tag or a szuru query. E.g. \'date:today tag-count:0\'')

        # Execute the parse_args() method
        args = parser.parse_args()

        self.sankaku_url = args.sankaku_url
        self.query       = args.query

    def parse_config(self):
        """
        Parse the user config and set the object attributes accordingly.
        """
        with open('config.json') as f:
            config = json.load(f)
        
        self.szuru_address     = config['szurubooru']['url']
        self.szuru_api_url     = self.szuru_address + '/api'
        self.szuru_api_token   = config['szurubooru']['api_token']
        self.szuru_headers     = {'Accept': 'application/json', 'Authorization': 'Token ' + self.szuru_api_token}
        self.szuru_public      = strtobool(config['szurubooru']['public'])
        self.preferred_booru   = config['auto_tagger'].get('preferred_booru', 'danbooru')
        self.fallback_booru    = config['auto_tagger'].get('fallback_booru', 'sankaku')
        self.local_temp_path   = config['auto_tagger'].get('local_temp_path', '/tmp/')
        self.saucenao_api_key  = config['auto_tagger']['saucenao_api_key']
        self.danbooru_user     = config['auto_tagger']['boorus']['danbooru'].get('user', 'None')
        self.danbooru_api_key  = config['auto_tagger']['boorus']['danbooru'].get('api_key', 'None')
        self.konachan_user     = config['auto_tagger']['boorus']['konachan'].get('user', 'None')
        self.konachan_pass     = config['auto_tagger']['boorus']['konachan'].get('password', 'None')
        self.yandere_user      = config['auto_tagger']['boorus']['yandere'].get('user', 'None')
        self.yandere_pass      = config['auto_tagger']['boorus']['yandere'].get('password', 'None')
        self.pixiv_user        = config['auto_tagger']['boorus']['pixiv'].get('user', 'None')
        self.pixiv_pass        = config['auto_tagger']['boorus']['pixiv'].get('password', 'None')
        self.pixiv_token       = config['auto_tagger']['boorus']['pixiv'].get('token', 'None')
        self.tagger_progress   = strtobool(config['auto_tagger'].get('show_progress', 'True'))
        self.uploader_progress = strtobool(config['upload_images'].get('show_progress', 'True'))
        self.upload_dir        = config['upload_images']['upload_dir']
        self.tags              = config['upload_images']['tags']
