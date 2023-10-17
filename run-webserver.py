from flask import Flask
from flask import request

from szurubooru_toolkit.scripts.import_from_url import main as import_from_url


app = Flask(__name__)


@app.route('/import-from-url', methods=['GET', 'POST'])
def run_import_from_url():
    current_url = request.args.get('url')
    cookie_location = request.args.get('cookies')
    limit_range = request.args.get('range')
    print(f'Downloading posts from {current_url}...')
    if cookie_location:
        print(f'Cookie file location: {cookie_location}')
    if limit_range:
        print(f'Limit range: {limit_range}')

    import_from_url([current_url], cookie_location, limit_range)
    return 'Script executed for URL: ' + current_url


if __name__ == '__main__':
    app.run()
