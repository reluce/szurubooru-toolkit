"""Webserver for the browser extensions, serving /import-from-url and /import-from-all-tabs.

Runs on the standard library only; the browser extensions expect it on http://localhost:5000.
"""

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import import_from_url as import_from_url_script


# Skip main's @logger.catch, which swallows errors: the response has to report failed imports
import_from_url = import_from_url_script.main.__wrapped__


# The configured cookies/range, captured before the first request overrides them
_configured = {}


def apply_overrides(params: dict) -> None:
    """Apply the cookies/range query params as config overrides; empty params restore the configured values."""

    if not _configured:
        _configured.update(cookies=config.import_from_url['cookies'], range=config.import_from_url['range'])

    overrides = {
        'globals': {'hide_progress': True},
        'import_from_url': {},
    }

    for key in ('cookies', 'range'):
        value = params.get(key) or _configured[key]
        overrides['import_from_url'][key] = value
        if params.get(key):
            logger.info(f'Using {key} "{value}"')

    config.override_config(overrides)


def is_allowed_origin(origin: str | None) -> bool:
    """Allows the browser extensions and non-browser clients (no Origin), but no web pages."""

    return origin is None or origin.startswith(('chrome-extension://', 'moz-extension://'))


class ToolkitRequestHandler(BaseHTTPRequestHandler):
    def _respond(self, body: str, status: int = 200) -> None:
        data = body.encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            self.send_header('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # Client (browser extension) gave up waiting during a long import; the work is done
            logger.debug('Client closed the connection before the response was sent')

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

        if parsed.path not in ('/import-from-url', '/import-from-all-tabs'):
            self._respond('Not found', 404)
        elif self.command != 'POST':
            # A GET could be triggered by any web page, e.g. via <img src>
            self._respond('Method not allowed', 405)
        elif not is_allowed_origin(self.headers.get('Origin')):
            # Browsers always send Origin on cross-origin POSTs; only the extensions may import
            self._respond('Forbidden', 403)
        elif parsed.path == '/import-from-url':
            self._handle_import_from_url(params)
        else:
            self._handle_import_from_all_tabs(params)

    def _handle_import_from_url(self, params: dict) -> None:
        current_url = params.get('url')
        if not current_url:
            self._respond('No URL provided', 400)
            return

        apply_overrides(params)
        try:
            import_from_url(urls=[current_url])
        except Exception as e:
            logger.exception(f'Failed to import from {current_url}: {e}')
            self._respond(f'Import failed for URL {current_url}: {e}', 500)
            return

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
                logger.exception(f'Failed to import from {url}: {e}')
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
