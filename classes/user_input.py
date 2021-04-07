import argparse
import configparser
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

        config = configparser.ConfigParser()

        config.read('config')
        self.booru_address   = config['szurubooru']['address']
        self.booru_api_url   = self.booru_address + '/api'
        self.booru_api_token = config['szurubooru']['api_token']
        self.booru_headers   = {'Accept': 'application/json', 'Authorization': 'Token ' + self.booru_api_token}
        self.booru_offline   = strtobool(config['szurubooru']['offline'])
        self.preferred_booru = config['options'].get('preferred_booru', 'danbooru')
        self.fallback_booru  = config['options'].get('fallback_booru', 'sankaku')
        self.upload_dir      = config['options']['upload_dir']
        self.tags            = config['options']['tags'].split(',')
        self.local_temp_path = config['options'].get('local_temp_path', 'tmp')

    def describe(self):
        """
        Prints the currently assigned attributes of the object.
        """

        data = {
            'booru_address': self.booru_address,
            'booru_api_url': self.booru_api_url,
            'booru_api_token': self.booru_api_token,
            'booru_headers': self.booru_headers,
            'booru_offline': self.booru_offline,
            'preferred_booru': self.preferred_booru,
            'fallback_booru': self.fallback_booru,
            'upload_dir': self.upload_dir,
            'tags': self.tags,
        }

        print(data)
