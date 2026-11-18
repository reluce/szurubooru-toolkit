# Installation and configuration

## Install the toolkit

The toolkit requires Python 3.11 or newer and a reachable szurubooru instance.
Install from [PyPI](https://pypi.org/project/szurubooru-toolkit/) in your
Python environment.

```sh
pip install szurubooru-toolkit
```

If you use local tagging or Pixiv metadata, choose the corresponding extra.
`wd-tagger` installs ONNX Runtime for CPU inference. `wd-tagger-cuda` installs
the NVIDIA variant. Install one WD extra per environment. Extras can be
combined with Pixiv support.

```sh
pip install "szurubooru-toolkit[wd-tagger,pixiv]"
```

From a source checkout, run `uv sync` in the repository root and use
`uv run szuru-toolkit` to run commands. For the same extras, use
`uv sync --extra wd-tagger --extra pixiv`. See [Docker](docker.md) for
container installation and [WD tagger](tagging.md#wd-tagger) for model and
hardware setup.

## Connect to szurubooru

Create a token in your szurubooru account settings. Use an account with
permissions for the operations you want to run, such as creating posts,
editing tags or deleting posts. Copy [config_sample.toml](../config_sample.toml)
to `config.toml` or start with these settings.

```toml
[globals]
url = "https://szuru.example.com"
username = "my_szuru_user"
api_token = "my_api_token"

[upload_media]
src_path = "./upload_src"
```

The URL is the base address of the board, including `http://` or
`https://`. Keep your API token and cookie files private. The URL, username
and token can also be supplied as global CLI options. Put global options
before the subcommand.

## Configuration lookup

The toolkit loads the first `config.toml` it finds, in this order.

| Priority | Linux and macOS | Windows |
| --- | --- | --- |
| 1 | Current working directory | Current working directory |
| 2 | `~/.config/szurubooru-toolkit/config.toml` | `%USERPROFILE%/szurubooru-toolkit/config.toml` |
| 3 | `/etc/szurubooru-toolkit/config.toml` | `%APPDATA%/szurubooru-toolkit/config.toml` |

Explicit CLI options override file values for that run. The
[sample configuration](../config_sample.toml) shows settings for individual
commands and can contain different choices from the built-in defaults.
The [configuration reference](configuration.md) explains each key.
Relative paths are resolved from the process working directory. On Windows,
use forward slashes in TOML path strings.

Both `szuru-toolkit` and `szuructl` invoke the same CLI. Use
`szuru-toolkit --help` to list commands and `szuru-toolkit COMMAND --help`
for flags and arguments. Quote queries containing spaces or shell wildcards.
Use `--` before a query that starts with a dash.

```sh
szuru-toolkit auto-tagger --dry-run -- "-tag_one tag_two"
```

## Optional service credentials

| Service | Setting | Used for |
| --- | --- | --- |
| SauceNAO | `[auto_tagger].saucenao_api_token` | API key for reverse image searches. Request limits depend on the account. |
| Pixiv | `[credentials.pixiv].token` | Pixiv refresh token for metadata lookups. Install the `pixiv` extra. |
| Gelbooru | `[credentials.gelbooru].user_id` and `api_key` | Gelbooru searches and imports. Uncomment the section in the sample to set both values. |
| Sankaku | `[credentials.sankaku].username` and `password` | The toolkit's Sankaku API lookups. For an authenticated page download, use gallery-dl cookies where required. |
| X and other download sites | `[import_from_url].cookies` or `--cookies` | Path to a Netscape-format cookie file for gallery-dl. |

When using SauceNAO with a publicly reachable board, `[globals].public = true`
allows SauceNAO to fetch a public post URL when the toolkit can use URL-based
search. For a private board, keep `public = false`. SauceNAO can still receive
image data for reverse search. Disable `saucenao` if you want to avoid these
requests.

## Logs and workers

The toolkit prints status to the terminal. To investigate a failing run,
enable a file log with `[logging].log_enabled = true` and set
`log_file`, `log_level` and `log_colorized` as needed. For one run you can
also set `--log-enabled --log-file toolkit.log --log-level DEBUG` before the
subcommand. Use `--hide-progress` before the subcommand to simplify scheduled
job output. Most commands that process batches support a `workers` setting
or `--workers`. Start with one worker on a small NAS or when troubleshooting.
