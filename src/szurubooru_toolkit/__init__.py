from szurubooru_toolkit.config import Config


def setup_config():
    global config

    config = Config()


def setup_logger() -> None:
    """Setup loguru logging handlers."""

    import sys

    from loguru import logger

    logger.remove(0)
    logger.add(
        sink=sys.stderr,
        backtrace=False,
        colorize=True,
        level='ERROR',
        enqueue=True,
        diagnose=False,
        format=''.join(
            '<lr>[{level}]</lr> <ly>[{module}.{function}]</ly>: {message}',
        ),
    )

    logger.configure(
        handlers=[
            dict(
                sink=config.logging['log_file'],
                colorize=config.logging['log_colorized'],
                level=config.logging['log_level'],
                diagnose=False,
                format=''.join(
                    '<lm>[{level}]</lm> <lg>[{time:DD.MM.YYYY, HH:mm:ss zz}]</lg> <ly>[{module}.{function}]</ly> {message}',
                ),
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='INFO',
                filter=lambda record: record['level'].no < 30,
                format='<le>[{level}]</le> {message}',
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='WARNING',
                filter=lambda record: record['level'].no < 40,
                format=''.join(
                    '<ly>[{level}]</ly> <ly>[{module}.{function}]</ly> {message}',
                ),
            ),
            dict(
                sink=sys.stderr,
                backtrace=False,
                diagnose=False,
                colorize=True,
                level='ERROR',
                format=''.join(
                    '<lr>[{level}]</lr> <ly>[{module}.{function}]</ly> {message}',
                ),
            ),
        ],
    )

    if not config.logging['log_enabled']:
        logger.remove(2)  # Assume id 2 is the handler with the log file sink


def setup_clients():
    from szurubooru_toolkit.danbooru import Danbooru  # noqa F401
    from szurubooru_toolkit.sankaku import Sankaku
    from szurubooru_toolkit.szurubooru import Szurubooru

    global danbooru, sankaku, szuru

    danbooru = Danbooru()
    sankaku = Sankaku()
    szuru = Szurubooru(config.globals['url'], config.globals['username'], config.globals['api_token'])
