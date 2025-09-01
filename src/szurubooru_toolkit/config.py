import os
import re
import tomllib
import urllib
from pathlib import Path

import validators
from loguru import logger
from validators import ValidationError


GLOBALS_DEFAULTS = {
    'url': None,
    'username': None,
    'api_token': None,
    'public': False,
    'hide_progress': False,
}

CREDENTIALS_DEFAULTS = {
    'pixiv': {'token': None},
    'sankaku': {'username': None, 'password': None},
}

LOGGING_DEFAULTS = {
    'log_enabled': False,
    'log_file': 'szurubooru_toolkit.log',
    'log_level': 'INFO',
    'log_colorized': True,
}

AUTO_TAGGER_DEFAULTS = {
    'saucenao_api_token': None,
    'saucenao': True,
    'md5_search': True,
    'deepbooru': False,
    'deepbooru_model': None,
    'deepbooru_threshold': 0.7,
    'deepbooru_forced': False,
    'deepbooru_set_tag': False,
    'default_safety': 'safe',
    'hide_progress': False,
    'use_pixiv_artist': False,
    'use_pixiv_tags': False,
    'update_relations': False,
    'limit': None,
}

CREATE_RELATIONS_DEFAULTS = {
    'threshold': 3,
    'hide_progress': False,
}

CREATE_TAGS_DEFAULTS = {
    'hide_progress': False,
    'limit': 100,
    'min_post_count': 10,
    'query': '*',
    'overwrite': False,
}

DELETE_POSTS_DEFAULTS = {'hide_progress': False}

IMPORT_FROM_BOORU_DEFAULTS = {
    'deepbooru': False,
    'limit': 100,
    'hide_progress': False,
    'tmp_path': './tmp/gallery-dl',
}

IMPORT_FROM_URL_DEFAULTS = {
    'cookies': None,
    'saucenao': False,
    'md5_search': False,
    'deepbooru': False,
    'hide_progress': False,
    'md5_search': False,
    'range': ':100',
    'saucenao': False,
    'tmp_path': './tmp/gallery-dl',
    'use_twitter_artist': False,
    'update_tags_if_exists': False,
}

RESET_POSTS_DEFAULTS = {'hide_progress': False}

TAG_POSTS_DEFAULTS = {
    'hide_progress': False,
    'update_implications': False,
    'mode': 'append',
    'silence_info': False,
}

UPLOAD_MEDIA_DEFAULTS = {
    'src_path': None,
    'hide_progress': False,
    'cleanup': False,
    'tags': ['tagme'],
    'auto_tag': False,
    'max_similarity': 0.95,
    'convert_to_jpg': False,
    'convert_threshold': '3MB',
    'convert_quality': 90,
    'shrink': False,
    'shrink_threshold': 6000000,
    'shrink_dimensions': '2500x2500',
    'default_safety': 'safe',
}


class Config:
    """Reference to the default config values and the user config (CLI/config.toml)."""

    def __init__(self) -> None:
        """
        Initializes a new instance of the Config class.

        This method sets the default configuration values for various components of the application. It also defines the
        default locations for the configuration file, which are different for Windows and Linux.

        The configuration values are stored as attributes of the Config instance. Each attribute is a dictionary containing
        the default configuration values for a specific component of the application.

        Args:
            None

        Returns:
            None
        """

        self.globals = GLOBALS_DEFAULTS
        self.logging = LOGGING_DEFAULTS
        self.auto_tagger = AUTO_TAGGER_DEFAULTS
        self.create_tags = CREATE_TAGS_DEFAULTS
        self.create_relations = CREATE_RELATIONS_DEFAULTS
        self.delete_posts = DELETE_POSTS_DEFAULTS
        self.import_from_booru = IMPORT_FROM_BOORU_DEFAULTS
        self.import_from_url = IMPORT_FROM_URL_DEFAULTS
        self.reset_posts = RESET_POSTS_DEFAULTS
        self.tag_posts = TAG_POSTS_DEFAULTS
        self.upload_media = UPLOAD_MEDIA_DEFAULTS
        self.credentials = CREDENTIALS_DEFAULTS

        # Define default locations for the config file
        if os.name == 'nt':  # Windows
            default_locations = [
                os.path.join(os.getcwd(), 'config.toml'),
                os.path.join(os.getenv('USERPROFILE'), 'szurubooru-toolkit', 'config.toml'),
                os.path.join(os.getenv('APPDATA'), 'szurubooru-toolkit', 'config.toml'),
            ]
        else:  # Linux
            default_locations = [
                os.path.join(os.getcwd(), 'config.toml'),
                os.path.expanduser('~/.config/szurubooru-toolkit/config.toml'),
                '/etc/szurubooru-toolkit/config.toml',
            ]

        for location in default_locations:
            if os.path.isfile(location):
                config_file = location
                break
            else:
                config_file = None

        if config_file:
            with open(config_file, 'rb') as f:
                try:
                    config = tomllib.load(f)
                    for section, values in config.items():
                        if hasattr(self, section):
                            getattr(self, section).update(values)
                except Exception as e:
                    logger.critical(e)
                    exit(1)

            self.validate_config()

    def override_config(self, overrides: dict) -> None:
        """Override options with command line arguments.

        Args:
            overrides (dict): A dictionary containing the options to override.
        """

        for section, items in overrides.items():
            section_dict = getattr(self, section)
            for item in items:
                section_dict[item] = items[item]
            setattr(self, section, section_dict)

            if section in ['import_from_booru', 'import_from_url']:
                self.update_upload_media_config(section)

        self.validate_config()

    def validate_path(self) -> None:
        """Check if the directories exist and create them if not."""

        src_path = Path(self.upload_media['src_path'])
        if not src_path.is_dir():
            logger.info(f'The src_path "{src_path}" does not exist. Creating it...')
            src_path.mkdir(parents=True)

        tmp_path = Path(self.import_from_url['tmp_path'])
        if not tmp_path.is_dir():
            logger.info(f'The tmp_path "{tmp_path}" does not exist. Creating it...')
            tmp_path.mkdir(parents=True)

        log_file_parent = Path(self.logging['log_file']).parent
        if not log_file_parent.is_dir():
            logger.info(f'The log_file\'s parent directory "{log_file_parent}" does not exist. Creating it...')
            log_file_parent.mkdir(parents=True)

    def validate_url(self) -> None:
        """Sanitize the szurubooru url.

        Make sure that the URL itself is valid, of scheme HTTP/s and remove trailing '/' char.
        """

        self.globals['url'] = self.globals['url'].strip()
        result = validators.url(self.globals['url'])

        if isinstance(result, ValidationError):
            logger.critical(f'Your szurubooru URL "{self.globals["url"]}" is not valid!')
            exit(1)

        parsed_url = urllib.parse.urlsplit(self.globals['url'])

        api_scheme = parsed_url.scheme
        if api_scheme not in ('http', 'https'):
            logger.critical('API URL must be of HTTP or HTTPS scheme!')
            exit(1)

        if parsed_url.path.startswith('/'):
            self.globals['url'] = self.globals['url'].rstrip('/')

    def validate_deepbooru(self) -> None:
        """Check if deepbooru_model is an existing file."""

        if not Path(self.auto_tagger['deepbooru_model']).exists():
            logger.critical(
                f'Your Deepbooru model "{self.auto_tagger["deepbooru_model"]}" does not exist!',
            )
            exit(1)

        deepbooru_path = Path(self.auto_tagger['deepbooru_model']).parent
        tags_file = deepbooru_path / 'tags.txt'
        if not tags_file.exists():
            logger.critical(
                f'File tags.txt not found. Place it in {deepbooru_path}.',
            )
            exit(1)

    def validate_convert_attrs(self) -> None:
        """Convert the threshold from a human readable to a machine readable size."""

        convert_threshold = self.upload_media['convert_threshold']

        # Since this function gets called twice (CLI param + config.toml check) we have to check if the value is already converted
        try:
            # Check if convert_threshold is already a number (converted previously)
            if isinstance(convert_threshold, (int, float)):
                # Already converted, skip validation
                pass
            elif not any(x in convert_threshold for x in ['KB', 'MB']):
                logger.critical(
                    f'Your convert_threshold "{self.upload_media["convert_threshold"]}" is not valid!',
                )
                exit(1)
            else:
                if 'KB' in convert_threshold:
                    self.upload_media['convert_threshold'] = float(convert_threshold.replace('KB', '')) * 1000
                elif 'MB' in convert_threshold:
                    self.upload_media['convert_threshold'] = float(convert_threshold.replace('MB', '')) * 1000000
        except TypeError:
            pass

        self.upload_media['convert_quality'] = int(self.upload_media['convert_quality'])

        if self.upload_media['convert_quality'] > 95:
            logger.critical(
                f'Your convert_quality value "{self.upload_media["convert_quality"]}" is higher than the max value of 95!',
            )
            exit(1)

    def validate_shrink_attrs(self) -> None:
        """Validate that the shink dimensions matches reg exp."""

        # Since this function gets called twice (CLI param + config.toml check) we have to check if the value is already converted
        try:
            # Check if shrink_dimensions is already a tuple (converted previously)
            if isinstance(self.upload_media['shrink_dimensions'], tuple):
                # Already converted, skip validation
                pass
            elif not re.match(r'\d+x\d+', self.upload_media['shrink_dimensions']):
                logger.critical(
                    f'Your shrink_dimensions "{self.upload_media["shrink_dimensions"]}" are not valid!',
                )
                exit(1)
            else:
                dimensions = re.search(r'(\d+)x(\d+)', self.upload_media['shrink_dimensions'])
                max_width = int(dimensions.group(1))
                max_height = int(dimensions.group(2))
                self.upload_media['shrink_dimensions'] = (int(max_width), int(max_height))
        except TypeError:
            pass

        self.upload_media['shrink_threshold'] = int(self.upload_media['shrink_threshold'])

    def validate_safety(self) -> None:
        """Check if default_safety is set correctly."""

        if not self.upload_media['default_safety'] in ['safe', 'sketchy', 'unsafe']:
            logger.critical(
                f'The default_safety "{self.upload_media["default_safety"]}" is not valid!',
            )
            logger.critical('Choose between safe, sketchy and unsafe.')
            exit(1)

    def validate_szurubooru(self) -> None:
        """Check if szurubooru options are set correctly."""

        if not self.globals['url'] or not self.globals['username'] or not self.globals['api_token']:
            logger.critical('You have to specify a szurubooru URL, username and API token!')
            exit(1)

    def validate_config(self) -> None:
        """Validate the config by calling the individual validation methods except the validate_path() method."""

        self.validate_szurubooru()
        self.validate_url()
        self.validate_safety()
        self.validate_convert_attrs()
        self.validate_shrink_attrs()

        if self.auto_tagger['deepbooru']:
            self.validate_deepbooru()
        else:
            self.auto_tagger['deepbooru_forced'] = False

    def update_upload_media_config(self, section: str) -> None:
        """
        Updates the upload media configuration with the options from the specified section.

        This method updates the upload media configuration (`self.upload_media`) with the options from the specified
        section. The section should be an attribute of `self` that is a dictionary. The options that are
        updated are 'max_similarity', 'convert_to_jpg', 'convert_threshold', 'convert_quality', 'shrink',
        'shrink_threshold', 'shrink_dimensions', and 'default_safety'. If an option does not exist in the section, it is
        ignored.

        Args:
            section (str): The name of the attribute of `self` that contains the section configuration.

        Raises:
            AttributeError: If `config_src` is not an attribute of `self`.
        """

        upload_media_options = [
            'max_similarity',
            'convert_to_jpg',
            'convert_threshold',
            'convert_quality',
            'shrink',
            'shrink_threshold',
            'shrink_dimensions',
            'default_safety',
        ]

        config_src_obj = getattr(self, section)

        for option in upload_media_options:
            try:
                self.upload_media[option] = config_src_obj[option]
            except AttributeError:
                pass
