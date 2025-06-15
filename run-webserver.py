from flask import Flask
from flask import request
from flask import jsonify
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

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/import-from-url', methods=['GET', 'POST', 'OPTIONS'])
def run_import_from_url():
    if request.method == 'OPTIONS':
        # Handle preflight request
        return '', 200
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
    import_from_url(urls=[current_url])

    return 'Script executed for URL: ' + current_url


@app.route('/import-from-all-tabs', methods=['POST', 'OPTIONS'])
def run_import_from_all_tabs():
    if request.method == 'OPTIONS':
        # Handle preflight request
        return '', 200
    cookie_location = request.args.get('cookies')
    range = request.args.get('range')
    
    # Get URLs from JSON body
    data = request.get_json()
    if not data or 'urls' not in data:
        return 'No URLs provided', 400
    
    urls = data['urls']
    logger.info(f'Importing from {len(urls)} tabs')

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
    
    # Process all URLs
    successful_imports = 0
    failed_imports = 0
    
    for url in urls:
        try:
            logger.info(f'Processing URL: {url}')
            import_from_url(urls=[url])
            successful_imports += 1
        except Exception as e:
            logger.error(f'Failed to import from {url}: {str(e)}')
            failed_imports += 1

    return f'Script executed for {len(urls)} URLs. Successful: {successful_imports}, Failed: {failed_imports}'


if __name__ == '__main__':
    app.run()
