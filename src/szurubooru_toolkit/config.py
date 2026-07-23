import copy
import os
import re
import tomllib
import urllib.parse
from pathlib import Path

from loguru import logger


# 'hide_progress' is deliberately absent: scripts try config.globals['hide_progress']
# first and fall back to their own section's value on KeyError, so a global default
# would silently override every per-section hide_progress setting.
GLOBALS_DEFAULTS = {
    'url': None,
    'username': None,
    'api_token': None,
    'public': False,
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
    'wd_tagger': False,
    'wd_tagger_model': 'SmilingWolf/wd-eva02-large-tagger-v3',
    'wd_tagger_providers': [],
    'wd_tagger_threshold': 0.35,
    'wd_tagger_character_threshold': 0.75,
    'wd_tagger_forced': False,
    'wd_tagger_set_tag': False,
    'wd_tagger_videos': True,
    'wd_tagger_review': False,
    'wd_tagger_review_threshold': 0.5,
    'dry_run': False,
    'default_safety': 'safe',
    'safety_overrides': {},
    'hide_progress': False,
    'use_pixiv_artist': False,
    'use_pixiv_tags': False,
    'update_relations': False,
    'limit': None,
    'workers': 4,
}

CREATE_RELATIONS_DEFAULTS = {
    'threshold': 3,
    'hide_progress': False,
}

FIX_RELATIONS_DEFAULTS = {
    'hide_progress': False,
}

CREATE_TAGS_DEFAULTS = {
    'hide_progress': False,
    'limit': 100,
    'min_post_count': 10,
    'query': '*',
    'overwrite': False,
    'import_implications': False,
}

DELETE_POSTS_DEFAULTS = {'hide_progress': False, 'workers': 4}

FIND_DUPLICATES_DEFAULTS = {
    'threshold': 4,
    'workers': 4,
    'limit': None,
    'set_relations': False,
    'hide_progress': False,
}

PREVIEW_TAGS_DEFAULTS = {
    'min_score': 0.1,
}

IMPORT_FROM_BOORU_DEFAULTS = {
    'wd_tagger': False,
    'limit': 100,
    'hide_progress': False,
    'tmp_path': './tmp/gallery-dl',
}

IMPORT_FROM_URL_DEFAULTS = {
    'cookies': None,
    'saucenao': False,
    'md5_search': False,
    'wd_tagger': False,
    'hide_progress': False,
    'range': ':100',
    'tmp_path': './tmp/gallery-dl',
    'use_twitter_artist': False,
    'update_tags_if_exists': False,
    'workers': 4,
}

RESET_POSTS_DEFAULTS = {'hide_progress': False, 'workers': 4}

TAG_POSTS_DEFAULTS = {
    'hide_progress': False,
    'update_implications': False,
    'mode': 'append',
    'silence_info': False,
    'workers': 4,
}

UPLOAD_MEDIA_DEFAULTS = {
    'src_path': None,
    'hide_progress': False,
    'cleanup': False,
    'tags': ['tagme'],
    'read_sidecar_tags': False,
    'update_tags_if_exists': False,
    'auto_tag': False,
    'max_similarity': 0.95,
    'convert_to_jpg': False,
    'convert_threshold': '3MB',
    'convert_quality': 90,
    'shrink': False,
    'shrink_threshold': 6000000,
    'shrink_dimensions': '2500x2500',
    'default_safety': 'safe',
    'workers': 4,
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

        # Deep copies so config file values and runtime overrides never mutate the
        # module-level default dicts (and with them every other Config instance)
        self.globals = copy.deepcopy(GLOBALS_DEFAULTS)
        self.logging = copy.deepcopy(LOGGING_DEFAULTS)
        self.auto_tagger = copy.deepcopy(AUTO_TAGGER_DEFAULTS)
        self.create_tags = copy.deepcopy(CREATE_TAGS_DEFAULTS)
        self.create_relations = copy.deepcopy(CREATE_RELATIONS_DEFAULTS)
        self.fix_relations = copy.deepcopy(FIX_RELATIONS_DEFAULTS)
        self.delete_posts = copy.deepcopy(DELETE_POSTS_DEFAULTS)
        self.find_duplicates = copy.deepcopy(FIND_DUPLICATES_DEFAULTS)
        self.preview_tags = copy.deepcopy(PREVIEW_TAGS_DEFAULTS)
        self.import_from_booru = copy.deepcopy(IMPORT_FROM_BOORU_DEFAULTS)
        self.import_from_url = copy.deepcopy(IMPORT_FROM_URL_DEFAULTS)
        self.reset_posts = copy.deepcopy(RESET_POSTS_DEFAULTS)
        self.tag_posts = copy.deepcopy(TAG_POSTS_DEFAULTS)
        self.upload_media = copy.deepcopy(UPLOAD_MEDIA_DEFAULTS)
        self.credentials = copy.deepcopy(CREDENTIALS_DEFAULTS)

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

        parsed_url = urllib.parse.urlsplit(self.globals['url'])

        if not parsed_url.netloc:
            logger.critical(f'Your szurubooru URL "{self.globals["url"]}" is not valid!')
            exit(1)

        if parsed_url.scheme not in ('http', 'https'):
            logger.critical('API URL must be of HTTP or HTTPS scheme!')
            exit(1)

        if parsed_url.path.startswith('/'):
            self.globals['url'] = self.globals['url'].rstrip('/')

    def validate_wd_tagger(self) -> None:
        """Check if wd_tagger_model is set to a Hugging Face repo id or an existing local model directory."""

        model = self.auto_tagger['wd_tagger_model']

        if not model:
            logger.critical('You have to specify a wd_tagger_model (Hugging Face repo id or local directory)!')
            exit(1)

        model_dir = Path(model)
        if model_dir.is_dir():
            for file in ['model.onnx', 'selected_tags.csv']:
                if not (model_dir / file).is_file():
                    logger.critical(f'Your WD tagger model directory "{model}" is missing {file}!')
                    exit(1)
        elif not re.match(r'^[\w.-]+/[\w.-]+$', model):
            logger.critical(
                f'Your wd_tagger_model "{model}" is neither an existing local directory nor a valid Hugging Face repo id!',
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
        """Check if default_safety and safety_overrides are set correctly."""

        if not self.upload_media['default_safety'] in ['safe', 'sketchy', 'unsafe']:
            logger.critical(
                f'The default_safety "{self.upload_media["default_safety"]}" is not valid!',
            )
            logger.critical('Choose between safe, sketchy and unsafe.')
            exit(1)

        for level, tags in self.auto_tagger['safety_overrides'].items():
            if level not in ['sketchy', 'unsafe']:
                logger.critical(f'The safety_overrides level "{level}" is not valid! Choose between sketchy and unsafe.')
                exit(1)
            if not isinstance(tags, list):
                logger.critical(f'safety_overrides.{level} has to be a list of tags!')
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

        if self.auto_tagger['wd_tagger']:
            self.validate_wd_tagger()
        else:
            self.auto_tagger['wd_tagger_forced'] = False

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
            except KeyError:
                pass
