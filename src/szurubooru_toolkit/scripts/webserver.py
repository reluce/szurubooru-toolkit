"""Webserver for the browser extensions, serving /import-from-url and /import-from-all-tabs.

Runs on the standard library only; the browser extensions expect it on http://localhost:5000.
"""

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit.scripts.import_from_url import main as import_from_url


def apply_overrides(params: dict) -> None:
    """Apply the cookies/range query params as config overrides."""

    overrides = {
        'globals': {'hide_progress': True},
        'import_from_url': {},
    }

    cookie_location = params.get('cookies')
    if cookie_location:
        overrides['import_from_url']['cookies'] = cookie_location
        logger.info(f'Cookie file location: "{cookie_location}"')

    range_ = params.get('range')
    if range_:
        overrides['import_from_url']['range'] = range_
        logger.info(f'Limit range: "{range_}"')

    config.override_config(overrides)


class ToolkitRequestHandler(BaseHTTPRequestHandler):
    def _respond(self, body: str, status: int = 200) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        logger.debug(f'{self.address_string()} - {format % args}')

    def do_OPTIONS(self) -> None:
        # CORS preflight
        self._respond('', 200)

    def do_GET(self) -> None:
        self._route()

    def do_POST(self) -> None:
        self._route()

    def _route(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        params = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}

        if parsed.path == '/import-from-url':
            self._handle_import_from_url(params)
        elif parsed.path == '/import-from-all-tabs':
            if self.command != 'POST':
                self._respond('Method not allowed', 405)
            else:
                self._handle_import_from_all_tabs(params)
        else:
            self._respond('Not found', 404)

    def _handle_import_from_url(self, params: dict) -> None:
        current_url = params.get('url')
        if not current_url:
            self._respond('No URL provided', 400)
            return

        apply_overrides(params)
        import_from_url(urls=[current_url])

        self._respond('Script executed for URL: ' + current_url)

    def _handle_import_from_all_tabs(self, params: dict) -> None:
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length else None
        except ValueError:
            data = None

        if not data or 'urls' not in data:
            self._respond('No URLs provided', 400)
            return

        urls = data['urls']
        logger.info(f'Importing from {len(urls)} tabs')

        apply_overrides(params)

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

        self._respond(f'Script executed for {len(urls)} URLs. Successful: {successful_imports}, Failed: {failed_imports}')


def main(host: str = '127.0.0.1', port: int = 5000) -> None:
    """
    Runs the webserver for the browser extensions.

    Args:
        host (str, optional): Address to bind to. Defaults to '127.0.0.1'.
        port (int, optional): Port to listen on. Defaults to 5000, which the browser
            extensions expect.

    Returns:
        None
    """

    try:
        logger.info(f'Listening on http://{host}:{port}')
        # Requests are handled serially on purpose: imports mutate the global config
        HTTPServer((host, port), ToolkitRequestHandler).serve_forever()
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(0)


if __name__ == '__main__':
    main()
