import argparse
import configparser
import json
from distutils.util import strtobool

class UserInput:
    def __init__(self):
        self.booru_address   = ''
        self.booru_api_token = ''
        self.booru_api_url   = ''
        self.booru_offline   = ''
        self.booru_headers   = ''
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

        self.booru_address     = config['szurubooru']['url']
        self.booru_api_url     = self.booru_address + '/api'
        self.booru_api_token   = config['szurubooru']['api_token']
        self.booru_headers     = {'Accept': 'application/json', 'Authorization': 'Token ' + self.booru_api_token}
        self.booru_offline     = strtobool(config['szurubooru']['external'])
        self.preferred_booru   = config['auto_tagger'].get('preferred_booru', 'danbooru')
        self.fallback_booru    = config['auto_tagger'].get('fallback_booru', 'sankaku')
        self.local_temp_path   = config['auto_tagger'].get('local_temp_path', 'tmp')
        self.danbooru_user     = config['auto_tagger']['boorus']['danbooru']['user']
        self.danbooru_api_key  = config['auto_tagger']['boorus']['danbooru']['api_key']
        self.konachan_user     = config['auto_tagger']['boorus']['konachan']['user']
        self.konachan_pass     = config['auto_tagger']['boorus']['konachan']['password']
        self.yandere_user      = config['auto_tagger']['boorus']['yandere']['user']
        self.yandere_pass      = config['auto_tagger']['boorus']['yandere']['password']
        self.use_saucenao      = strtobool(config['auto_tagger'].get('use_saucenao', 'True'))
        self.tagger_progress   = strtobool(config['auto_tagger'].get('show_progress', 'True'))
        self.uploader_progress = strtobool(config['upload_images'].get('show_progress', 'True'))
        self.upload_dir        = config['upload_images']['upload_dir']
        self.tags              = config['upload_images']['tags']
