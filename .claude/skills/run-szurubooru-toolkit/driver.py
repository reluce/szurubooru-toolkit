#!/usr/bin/env python3
"""Drive szuru-toolkit against a fake szurubooru API server (stdlib only).

Modes:
  python3 driver.py smoke        # default: full tag-posts flow, asserts the PUT
  python3 driver.py serve [port] # keep the fake booru running; poke it manually

The fake server implements just enough of the szurubooru API for read/tag flows:
  GET /api/posts/?query=...   -> {'total': N, 'results': [...]}  (supports id:N)
  GET /api/post/<id>          -> single post resource
  PUT /api/post/<id>          -> records payload, bumps version
  DELETE /api/post/<id>       -> removes the post

Every mutating request is printed to stdout, so you can see what the CLI did.

The CLI is invoked from a throwaway cwd containing a hermetic config.toml so the
user's real config in ~/.config/szurubooru-toolkit/ is never picked up.
"""

import json
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[3]


def seed_posts() -> dict:
    posts = {}
    for post_id in (1, 2, 3):
        posts[post_id] = {
            'id': post_id,
            'source': f'https://example.com/{post_id}',
            'contentUrl': f'data/posts/{post_id}.jpg',
            'version': 1,
            'relations': [],
            'checksumMD5': f'md5-{post_id}',
            'type': 'image',
            'safety': 'safe',
            'tags': [{'names': ['tagme'], 'category': 'default', 'usages': 1}],
        }
    return posts


class FakeSzurubooru(BaseHTTPRequestHandler):
    posts = seed_posts()
    mutations = []  # (method, path, payload) of every PUT/DELETE

    def log_message(self, fmt, *args):  # silence default request logging
        pass

    def _send(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/api/posts/':
            query = parse_qs(url.query).get('query', [''])[0]
            id_match = re.search(r'(?<!\\)\bid:(\d+)', query)
            if id_match:
                results = [p for pid, p in self.posts.items() if pid == int(id_match.group(1))]
            else:
                results = list(self.posts.values())
            self._send({'total': len(results), 'results': results})
        elif url.path.startswith('/api/post/'):
            post_id = int(url.path.rsplit('/', 1)[1])
            if post_id in self.posts:
                self._send(self.posts[post_id])
            else:
                self._send({'name': 'PostNotFoundError', 'title': 'not found', 'description': 'Post not found.'}, 404)
        else:
            self._send({'name': 'ValidationError', 'title': 'bad path', 'description': f'Unhandled GET {url.path}'}, 404)

    def do_PUT(self):
        post_id = int(urlparse(self.path).path.rsplit('/', 1)[1])
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        print(f'[fake-booru] PUT /api/post/{post_id} {json.dumps(payload)}', flush=True)
        FakeSzurubooru.mutations.append(('PUT', self.path, payload))
        post = self.posts[post_id]
        post['version'] += 1
        if 'tags' in payload:
            post['tags'] = [{'names': [t], 'category': 'default', 'usages': 1} for t in payload['tags']]
        if 'source' in payload:
            post['source'] = payload['source']
        self._send(post)

    def do_DELETE(self):
        post_id = int(urlparse(self.path).path.rsplit('/', 1)[1])
        print(f'[fake-booru] DELETE /api/post/{post_id}', flush=True)
        FakeSzurubooru.mutations.append(('DELETE', self.path, None))
        self.posts.pop(post_id, None)
        self._send({})


def start_server(port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(('127.0.0.1', port), FakeSzurubooru)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_cli(url: str, args: list) -> subprocess.CompletedProcess:
    """Run szuru-toolkit from a throwaway cwd so no real config.toml leaks in."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'config.toml').write_text(
            f'[globals]\nurl = "{url}"\nusername = "smoke"\napi_token = "smoketoken"\n',
        )
        cmd = ['uv', 'run', '--project', str(REPO), 'szuru-toolkit', '--hide-progress', *args]
        print(f'[driver] $ {" ".join(cmd)}', flush=True)
        return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=120)


def smoke() -> int:
    server = start_server()
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'[driver] fake szurubooru listening on {url}')

    result = run_cli(url, ['tag-posts', '--add-tags', 'smoke_tag', '1'])
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)

    puts = [m for m in FakeSzurubooru.mutations if m[0] == 'PUT']
    assert result.returncode == 0, f'CLI exited {result.returncode}'
    assert len(puts) == 1, f'expected exactly 1 PUT, got {len(puts)}'
    assert 'smoke_tag' in puts[0][2]['tags'], f'smoke_tag missing from PUT payload: {puts[0][2]}'
    assert 'tagme' in puts[0][2]['tags'], 'append mode should keep existing tags'
    assert 'Finished tagging' in result.stderr

    server.shutdown()
    print('[driver] SMOKE PASS: tag-posts added smoke_tag to post 1 via PUT /api/post/1')
    return 0


def serve(port: int = 8899) -> int:
    server = start_server(port)
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'[driver] fake szurubooru listening on {url} (posts 1-3 seeded, Ctrl-C to stop)')
    print(f'[driver] example: uv run szuru-toolkit --url {url} --username smoke --api-token t tag-posts --add-tags foo "id:2"')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'smoke'
    if mode == 'serve':
        sys.exit(serve(*[int(a) for a in sys.argv[2:3]]))
    sys.exit(smoke())
