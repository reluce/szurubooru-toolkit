<p align="center">
<img src="https://cdn-icons-png.flaticon.com/512/2581/2581053.png"
  alt="szurubooru-toolkit icon"
  width="128" height="128">
</p>

# szurubooru-toolkit

A command-line toolkit for managing a [szurubooru](https://github.com/rr-/szurubooru)
image board. Import media from URLs, other boorus, local folders or browser
tabs. Tag posts with source metadata, reverse image search or the local WD
tagger, and maintain duplicates, tags and relations.

## Quick start

With Python 3.11 or newer, install the package from
[PyPI](https://pypi.org/project/szurubooru-toolkit/).

```sh
pip install szurubooru-toolkit
```

Copy [config_sample.toml](config_sample.toml) to `config.toml` and fill in
`url`, `username` and `api_token` under `[globals]`. To try a read-only command
against your board, scan up to 20 recent images for duplicates.

```sh
szuru-toolkit find-duplicates --limit 20 --no-set-relations "date:today"
szuru-toolkit --help
```

`szuructl` is a shorter alias. From a source checkout, run `uv sync` and prefix
the commands with `uv run`. See the installation guide for optional WD and
Pixiv support.

## Documentation

| Guide | Topics |
| --- | --- |
| [Installation and configuration](docs/setup.md) | Installation options, API credentials, configuration lookup and logs |
| [Importing and uploading](docs/importing.md) | URLs, booru queries, cookies, recurring feeds, upload retries and local folders |
| [Tagging and tag management](docs/tagging.md) | Automatic tagging, WD models, score previews, tag categories and bulk tag edits |
| [Board maintenance](docs/maintenance.md) | Duplicate detection, post relations, Sankaku source repair, resets and deletion |
| [Docker and scheduled jobs](docs/docker.md) | Image variants, volumes, cron, model caching and GPU setup |
| [Browser imports](docs/browser-extensions.md) | Chrome, Firefox and the local webserver |

For packaged installs, the guides are also available under
[Documentation on GitHub](https://github.com/reluce/szurubooru-toolkit#documentation).

## Image credit

Repository icon by [Flaticon](https://www.flaticon.com/free-icons-png/512/2581/2581053.png).
