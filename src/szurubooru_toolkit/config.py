import urllib
from pathlib import Path

import validators
from loguru import logger
from tomlkit import parse
from validators import ValidationFailure


class Config:
    """Holds the options set in config.toml as attributes."""

    def __init__(self) -> None:
        """Parse the user config (config.toml) and set this objects attributes accordingly."""

        try:
            with open('config.toml') as f:
                content = f.read()

                try:
                    self.config = parse(content)
                except Exception as e:
                    logger.critical(e)
                    exit()
        except FileNotFoundError as e:
            logger.critical(e)
            exit()

        for key, value in self.config.items():
            setattr(self, key, value)

        self.check_attr_set()
        self.validate_path()
        self.validate_url()

        if self.auto_tagger['deepbooru_enabled']:
            self.validate_deepbooru()
        else:
            self.auto_tagger['deepbooru_forced'] = False

    def check_attr_set(self) -> None:
        """Check if necessary options in config.toml are set."""

        req_opts = {
            'szurubooru': ['url', 'username', 'api_token', 'public'],
            'auto_tagger': [
                'saucenao_api_token',
                'saucenao_enabled',
                'deepbooru_enabled',
                'deepbooru_model',
                'deepbooru_threshold',
                'deepbooru_forced',
                'hide_progress',
                'tmp_path',
            ],
            'upload_media': ['src_path', 'hide_progress', 'cleanup', 'tags', 'auto_tag'],
            'logging': ['log_enabled', 'log_file', 'log_level', 'log_colorized'],
            'danbooru': ['user', 'api_key'],
            'gelbooru': ['user', 'api_key'],
            'konachan': ['user', 'password'],
            'yandere': ['user', 'password'],
            'pixiv': ['user', 'password', 'token'],
        }

        for section in req_opts:
            try:
                getattr(self, section)
            except AttributeError:
                logger.critical(f'The section "{section}" is not defined config.toml!')
                exit()

        for section, options in req_opts.items():
            for option in options:
                if option not in getattr(self, section):
                    logger.critical(
                        f'The option "{option}" in the "{section}" section was not set in config.toml! '
                        'Check the README for additional information.',
                    )
                    exit()

    def validate_path(self) -> None:
        """Check if the directories in config.toml exist.

        Paths have to exist, even if one is not being actively used.
        """

        if not Path(self.auto_tagger['tmp_path']).is_dir():
            logger.critical(f'The tmp_path "{self.auto_tagger["tmp_path"]}" specified in config.toml does not exist!')
            exit()

        if not Path(self.upload_media['src_path']).is_dir():
            logger.critical(f'The src_path "{self.upload_media["src_path"]}" specified in config.toml does not exist!')
            exit()

        if not Path(self.logging['log_file']).parent.is_dir():
            logger.critical(
                f'The log_file\'s parent directory "{Path(self.logging["log_file"]).parent}" '
                'specified in config.toml does not exist!',
            )
            exit()

    def validate_url(self) -> None:
        """Sanitize the szurubooru url in config.toml.

        Make sure that the URL itself is valid, of scheme HTTP/s and remove trailing '/' char.
        """

        self.szurubooru['url'] = self.szurubooru['url'].strip()
        result = validators.url(self.szurubooru['url'])

        if isinstance(result, ValidationFailure):
            logger.critical(f'Your szurubooru URL "{self.szurubooru["url"]}" in config.toml is not valid!')
            exit()

        parsed_url = urllib.parse.urlsplit(self.szurubooru['url'])

        api_scheme = parsed_url.scheme
        if api_scheme not in ('http', 'https'):
            logger.critical('API URL must be of HTTP or HTTPS scheme!')
            exit()

        if parsed_url.path.startswith('/'):
            self.szurubooru['url'] = self.szurubooru['url'].rstrip('/')

    def validate_deepbooru(self) -> None:
        """Check if deepbooru_model in config.toml is an existing file."""

        if not Path(self.auto_tagger['deepbooru_model']).exists():
            logger.critical(
                f'Your Deepbooru model "{self.auto_tagger["deepbooru_model"]}" in config.toml does not exist!',
            )
            exit()
