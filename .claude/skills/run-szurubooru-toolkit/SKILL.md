---
name: run-szurubooru-toolkit
description: Run, drive, and smoke-test the szuru-toolkit CLI locally against a fake szurubooru API server — no real szurubooru instance or Docker needed. Use when asked to run the app, verify a CLI change end-to-end, or test commands like tag-posts against a live server.
---

# Run szurubooru-toolkit

`szuru-toolkit` is a click-based Python CLI (managed with **uv**) that talks to a
szurubooru image-board server over HTTP. There is no local szurubooru instance and
Docker is not running, so the way to drive it for real is the committed driver:
a stdlib fake szurubooru API server the CLI runs against end-to-end.

All paths below are relative to the repo root.

## Prerequisites

- `uv` (present at `~/.local/bin/uv`)
- `uv sync` — installs the package + dev deps (WD-tagger/Pixiv extras not needed for this)

## Run (agent path) — the driver

```bash
uv sync
python3 .claude/skills/run-szurubooru-toolkit/driver.py smoke
```

This starts a fake szurubooru on an ephemeral port, runs
`szuru-toolkit tag-posts --add-tags smoke_tag 1` against it via subprocess, and
asserts the CLI issued exactly one `PUT /api/post/1` whose tags contain
`smoke_tag` (and kept `tagme`, i.e. append mode). Success ends with
`SMOKE PASS`. Every mutating request the CLI makes is echoed as
`[fake-booru] PUT ...` lines.

To poke arbitrary commands interactively, keep the fake booru running:

```bash
python3 .claude/skills/run-szurubooru-toolkit/driver.py serve 8899 &
uv run szuru-toolkit --url http://127.0.0.1:8899 --username smoke --api-token t \
    --hide-progress tag-posts --add-tags foo "id:2"
```

The fake server seeds posts 1–3 and implements `GET /api/posts/`,
`GET/PUT/DELETE /api/post/<id>` — enough for `tag-posts`, `reset-posts`,
`delete-posts` style flows. Extend `FakeSzurubooru` in
[driver.py](driver.py) when a command needs more endpoints (e.g. tags API).

## Direct invocation (internals)

Most PRs touch client/util internals; the test suite covers that layer with
`httpx.MockTransport` (no network):

```bash
uv run pytest -q          # 165 tests, ~1s
```

See `tests/test_szurubooru_client.py` for the `RecordingClient` pattern — the
right harness for testing new `Szurubooru` client methods.

## Run (human path)

`uv run szuru-toolkit <command>` against a real instance configured in
`config.toml` / `~/.config/szurubooru-toolkit/config.toml`. Useless here — no
real instance to hit (and you must not hit the owner's).

## Gotchas

- **`~/.config/szurubooru-toolkit/config.toml` exists on this machine and
  points at the owner's real instance.** A bare `uv run szuru-toolkit ...`
  without `--url/--username/--api-token` will target it. Never run mutating
  commands without explicit `--url` to the fake server. The driver additionally
  runs the CLI from a throwaway cwd containing its own `config.toml` (cwd
  config wins over the home one).
- **`config.toml` in the repo root is an empty *directory*** (docker
  bind-mount artifact). Config loading uses `os.path.isfile`, so it's silently
  skipped — running from repo root still falls through to the home config.
- Config resolution order: `./config.toml` → `~/.config/szurubooru-toolkit/config.toml`
  → `/etc/szurubooru-toolkit/config.toml`; CLI flags override only what they name.
- Client init makes no API calls — `--url` can point anywhere until a command
  actually fires requests. Numeric queries are rewritten to `id:N` by
  `Szurubooru.get_posts`.
- `import-from-booru`, `import-from-url`, `auto-tagger` (SauceNAO/MD5 search)
  need external network/services; `preview-tags` and WD-tagger options need the
  `wd-tagger` extra (`uv sync --all-extras`) and download an ONNX model from
  Hugging Face. Not covered by the driver.

## Troubleshooting

- `You have to specify a szurubooru URL, username and API token!` — no config
  file found in the cwd chain and flags missing. Pass all three flags or run
  via the driver.
- CLI output (loguru) goes to **stderr**; `Found N posts` / `Finished tagging!`
  won't show up if you only capture stdout.
