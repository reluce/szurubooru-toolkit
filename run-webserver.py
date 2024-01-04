from flask import Flask
from flask import request
from loguru import logger

from szurubooru_toolkit import setup_clients
from szurubooru_toolkit import setup_config
from szurubooru_toolkit import setup_logger


setup_config()
setup_logger()
setup_clients()

from szurubooru_toolkit import config  # noqa: E402
from szurubooru_toolkit.scripts.import_from_url import main as import_from_url  # noqa: E402


app = Flask(__name__)


@app.route('/import-from-url', methods=['GET', 'POST'])
def run_import_from_url():
    current_url = request.args.get('url')
    cookie_location = request.args.get('cookies')
    range = request.args.get('range')

    overrides = {
        'globals': {'hide_progress': True},
        'import_from_url': {},
    }

    if cookie_location:
        overrides['import_from_url']['cookies'] = cookie_location
        logger.info(f'Cookie file location: "{cookie_location}"')

    if range:
        overrides['import_from_url']['range'] = range
        logger.info(f'Limit range: "{range}"')

    config.override_config(overrides)
    config.validate_config()
    import_from_url(urls=[current_url])

    return 'Script executed for URL: ' + current_url


if __name__ == '__main__':
    app.run()
