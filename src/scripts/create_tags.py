from loguru import logger

from szuru_toolkit import Config
from szuru_toolkit import Szurubooru
from szuru_toolkit import setup_logger


def main():
    """Create or update tags. TODO with pyszuru package"""

    config = Config()
    setup_logger()
    logger.info('Initializing script...')
    szuru = Szurubooru(config.szurubooru['url'], config.szurubooru['username'], config.szurubooru['api_token'])  # noqa


if __name__ == '__main__':
    main()
