import re
import tomllib
import urllib
from pathlib import Path

import validators
from loguru import logger
from validators import ValidationFailure


class Config:
    """Holds the options set in config.toml as attributes."""

    def __init__(self, config_file: str = 'config.toml') -> None:
        """Parse the user config (config.toml) and set this objects attributes accordingly."""

        try:
            with open(config_file, 'rb') as f:
                try:
                    self.config = tomllib.load(f)
                except Exception as e:
                    logger.critical(e)
                    exit(1)
        except FileNotFoundError as e:
            logger.critical(e)
            exit(1)

        for key, value in self.config.items():
            setattr(self, key, value)

        self.check_attr_set()
        self.validate_path()
        self.validate_url()
        self.validate_safety()

        if self.upload_media['convert_to_jpg']:
            self.validate_convert_attrs()

        if self.auto_tagger['deepbooru_enabled']:
            self.validate_deepbooru()
        else:
            self.auto_tagger['deepbooru_forced'] = False

        if self.upload_media['shrink']:
            self.validate_shrink_attrs()

    def check_attr_set(self) -> None:
        """Check if necessary options in config.toml are set."""

        req_opts = {
            'szurubooru': ['url', 'username', 'api_token', 'public'],
            'auto_tagger': [
                'saucenao_api_token',
                'saucenao_enabled',
                'md5_search_enabled',
                'deepbooru_enabled',
                'deepbooru_model',
                'deepbooru_threshold',
                'deepbooru_forced',
                'deepbooru_set_tag',
                'hide_progress',
                'use_pixiv_artist',
                'update_relations',
            ],
            'upload_media': [
                'src_path',
                'hide_progress',
                'cleanup',
                'tags',
                'max_similarity',
                'auto_tag',
                'convert_to_jpg',
                'convert_threshold',
                'convert_quality',
                'shrink',
                'shrink_threshold',
                'shrink_dimensions',
                'default_safety',
            ],
            'import_from_booru': ['deepbooru_enabled', 'hide_progress'],
            'import_from_twitter': ['saucenao_enabled', 'deepbooru_enabled', 'hide_progress'],
            'import_from_url': ['deepbooru_enabled', 'hide_progress', 'tmp_path', 'use_twitter_artist'],
            'tag_posts': ['hide_progress'],
            'delete_posts': ['hide_progress'],
            'reset_posts': ['hide_progress'],
            'create_tags': ['hide_progress'],
            'create_relations': ['threshold'],
            'logging': ['log_enabled', 'log_file', 'log_level', 'log_colorized'],
            'danbooru': ['user', 'api_key'],
            'gelbooru': ['user', 'api_key'],
            'konachan': ['user', 'password'],
            'yandere': ['user', 'password'],
            'sankaku': ['user', 'password'],
            'pixiv': ['user', 'password', 'token'],
            'twitter': ['user_id', 'consumer_key', 'consumer_secret', 'access_token', 'access_token_secret'],
        }

        for section in req_opts:
            try:
                getattr(self, section)
            except AttributeError:
                logger.critical(f'The section "{section}" is not defined config.toml!')
                exit(1)

        for section, options in req_opts.items():
            for option in options:
                if option not in getattr(self, section):
                    logger.critical(
                        f'The option "{option}" in the "{section}" section was not set in config.toml! '
                        'Check the README for additional information.',
                    )
                    exit(1)

    def validate_path(self) -> None:
        """Check if the directories in config.toml exist.

        Paths have to exist, even if one is not being actively used.
        """

        if not Path(self.upload_media['src_path']).is_dir():
            logger.critical(f'The src_path "{self.upload_media["src_path"]}" specified in config.toml does not exist!')
            exit(1)

        if not Path(self.import_from_url['tmp_path']).is_dir():
            logger.critical(
                f'The tmp_path "{self.import_from_url["tmp_path"]}" specified in config.toml does not exist!',
            )
            exit(1)

        if not Path(self.logging['log_file']).parent.is_dir():
            logger.critical(
                f'The log_file\'s parent directory "{Path(self.logging["log_file"]).parent}" '
                'specified in config.toml does not exist!',
            )
            exit(1)

    def validate_url(self) -> None:
        """Sanitize the szurubooru url in config.toml.

        Make sure that the URL itself is valid, of scheme HTTP/s and remove trailing '/' char.
        """

        self.szurubooru['url'] = self.szurubooru['url'].strip()
        result = validators.url(self.szurubooru['url'])

        if isinstance(result, ValidationFailure):
            logger.critical(f'Your szurubooru URL "{self.szurubooru["url"]}" in config.toml is not valid!')
            exit(1)

        parsed_url = urllib.parse.urlsplit(self.szurubooru['url'])

        api_scheme = parsed_url.scheme
        if api_scheme not in ('http', 'https'):
            logger.critical('API URL must be of HTTP or HTTPS scheme!')
            exit(1)

        if parsed_url.path.startswith('/'):
            self.szurubooru['url'] = self.szurubooru['url'].rstrip('/')

    def validate_deepbooru(self) -> None:
        """Check if deepbooru_model in config.toml is an existing file."""

        if not Path(self.auto_tagger['deepbooru_model']).exists():
            logger.critical(
                f'Your Deepbooru model "{self.auto_tagger["deepbooru_model"]}" in config.toml does not exist!',
            )
            exit(1)

    def validate_convert_attrs(self) -> None:
        """Convert the threshold from a human readable to a machine readable size."""

        human_readable = self.upload_media['convert_threshold']

        if not any(x in human_readable for x in ['KB', 'MB']):
            logger.critical(
                f'Your convert_threshold "{self.upload_media["convert_threshold"]}" in config.toml is not valid!',
            )
            exit(1)

        if 'KB' in human_readable:
            self.upload_media['convert_threshold'] = float(human_readable.replace('KB', '')) * 1000
        elif 'MB' in human_readable:
            self.upload_media['convert_threshold'] = float(human_readable.replace('MB', '')) * 1000000

        if not self.upload_media['convert_quality'].isnumeric():
            logger.critical(
                f'Your convert_quality "{self.upload_media["convert_quality"]}" in config.toml \
                    is not a numeric value!',
            )
            exit(1)
        else:
            self.upload_media['convert_quality'] = int(self.upload_media['convert_quality'])

        if self.upload_media['convert_quality'] > 95:
            logger.critical(
                f'Your convert_quality value "{self.upload_media["convert_quality"]}" in config.toml \
                    is higher than the max value of 95!',
            )
            exit(1)

    def validate_shrink_attrs(self) -> None:
        """Validate that the shink dimensions matches reg exp."""

        if not re.match(r'\d+x\d+', self.upload_media['shrink_dimensions']):
            logger.critical(
                f'Your shrink_dimensions "{self.upload_media["shrink_dimensions"]}" in config.toml are not valid!',
            )
            exit(1)
        else:
            dimensions = re.search(r'(\d+)x(\d+)', self.upload_media['shrink_dimensions'])
            max_width = int(dimensions.group(1))
            max_height = int(dimensions.group(2))
            self.upload_media['shrink_dimensions'] = (int(max_width), (max_height))

        if not self.upload_media['shrink_threshold'].isnumeric():
            logger.critical(
                f'Your shrink_threshold "{self.upload_media["shrink_dimensions"]}" in config.toml \
                    is not a numeric value!',
            )
            exit(1)
        else:
            self.upload_media['shrink_threshold'] = int(self.upload_media['shrink_threshold'])

    def validate_safety(self) -> None:
        """Check if default_safety in config.toml is set correctly."""

        if not self.upload_media['default_safety'] in ['safe', 'sketchy', 'unsafe']:
            logger.critical(
                f'The default_safety "{self.upload_media["default_safety"]}" in config.toml is not valid!',
            )
            logger.critical('Choose between safe, sketchy and unsafe.')
            exit(1)
