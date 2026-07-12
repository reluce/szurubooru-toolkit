<p align="center">
<img src="https://cdn-icons-png.flaticon.com/512/2581/2581053.png"
  alt="szurubooru-toolkit icon"
  width="128" height="128">
</p>

# szurubooru-toolkit
Python package and script collection to manage your [szurubooru](https://github.com/rr-/szurubooru) image board.
```
Usage: szuru-toolkit [OPTIONS] COMMAND [ARGS]...

  Toolkit to manage your szurubooru image board.

  Defaults can also be set in a config file.

  Visit https://github.com/reluce/szurubooru-toolkit for more information.

Options:
  --url TEXT                      Base URL to your szurubooru instance.
  --username TEXT                 Username which will be used to authenticate with the szurubooru API.
  --api-token TEXT                API token for the user which will be used to authenticate with the
                                  szurubooru API.
  --public                        If your szurubooru instance is reachable from the internet (default:
                                  False).
  --log-enabled                   Create a log file (default: False).
  --log-colorized                 Colorize the log output (default: True).
  --log-file TEXT                 Output file for the log (default: szurubooru_toolkit.log)
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Set the log level (default: INFO).
  --hide-progress                 Hides the progress bar (default: False).
  -h, --help                      Show this message and exit.

Commands:
  auto-tagger        Tag posts automatically
  create-relations   Create relations between character and parody tag categories
  create-tags        Create tags based on a tag file or query
  delete-posts       Delete posts
  find-duplicates    Find visually duplicate posts via perceptual hashing
  fix-relations      Complete post relation sets via transitive closure
  import-from-booru  Download and tag posts from various Boorus
  import-from-url    Download images from URLS or file containing URLs
  preview-tags       Show WD tagger scores near the thresholds without tagging anything
  reset-posts        Remove tags and sources
  tag-posts          Tag posts manually
  upload-media       Upload media files
  webserver          Run the webserver for the browser extensions
```
## :ballot_box_with_check: Requirements
In order to run `szuru-toolkit`, Python `3.11` or newer is required.

## :hammer_and_wrench: Installation
This package is available on [PyPI](https://pypi.org/project/szurubooru-toolkit/) and can be installed with pip:
`pip install szurubooru-toolkit`

The WD tagger (local machine learning tagging) and Pixiv support are optional extras since they pull in heavy dependencies:

* `pip install "szurubooru-toolkit[wd-tagger]"` for WD tagger support (installs ONNX Runtime)
* `pip install "szurubooru-toolkit[pixiv]"` for Pixiv metadata support
* `pip install "szurubooru-toolkit[wd-tagger,pixiv]"` for both

Alternatively, you can clone the package from GitHub and set everything up with [uv](https://docs.astral.sh/uv/). In the root directory of this repository, execute `uv sync` (add `--all-extras` for WD tagger and Pixiv support).

### Docker Instructions
If you would like to run the toolkit in a Docker container instead, follow the
instructions below.
<details>
1. Copy `docker-compose.yml` to the location where you want to run the toolkit.

1. Copy `config_sample.toml` to the same location, renaming to `config.toml` and
replacing with your configuration.

1. Copy `crontab_sample` to the same location, renaming to `crontab` and adding
   the commands you would like to run regularly. An example command is provided
   in `crontab_sample`.

1. Make sure to set the `src_path` option in `config.toml` to use
   `/szurubooru-toolkit/upload_src`. If you're using a different directory than
   `upload_src`, you may need to update the `docker-compose.yml` binding to be
   something like `./uploads:/szurubooru-toolkit/uploads`, and set
   `/szurubooru-toolkit/uploads` as the `src_path` option instead.

1. Create the folder `tmp` in the same location.

1. If you would like to use tag files, create `misc/tags` in the same location
   and follow the instructions linked below

1. Run `touch szurubooru_toolkit.log` in the same location to create a file for
   the log. You may need to set the log location to
   `/szurubooru-toolkit/szurubooru_toolkit.log` in `config.toml`

1. Use `docker-compose up` or `docker-compose up -d` to start the container, or
   start the container in the background, respectively. You can use
   `docker-compose logs` or `docker-compose logs -f` to inspect the container
   output, which will include szuru toolkit's output if you append your cron
   jobs with `>/proc/1/fd/1 2>&1` like in the example job.

1. If you just want to run a one-time command, leave the `crontab` file blank
   and start the container with `docker-compose up -d`, taking note of the
   `container_name` option in `docker-compose.yml`. Then, you can run commands
   inside of the running container like this: `docker exec -it container_name
   uv run szuru-toolkit auto-tagger`, replacing `container_name` with the container name.

1. If you would like the container to run a one-time command and then quit with
   `docker-compose.yml`, add a `command` configuration [like
   this](https://docs.docker.com/compose/compose-file/compose-file-v3/#command).
</details>

## :memo: User configuration
While the script `szuru-toolkit` can run with just command line options, you can also set your options in a config file.

The script looks for a `config.toml` file in following locations:

### Linux
* Your current working directory from which `szuru-toolkit` is executed
* `~/.config/szurubooru-toolkit/config.toml`
* `/etc/szurubooru-toolkit/config.toml`

### Windows
* Your current working directory from which `szuru-toolkit` is executed
* `$USERPROFILE/szurubooru-toolkit/config.toml`
* `$APPDATA/szurubooru-toolkit/config.toml`

Options passed to the `szuru-toolkit` script take priority over the config file.

You can find a sample config file in the [GitHub repository](https://github.com/reluce/szurubooru-toolkit) of this package.

Note that path names have to be specified with forward slashes (/) if you're using Windows.

Creating a SauceNAO account and an API key is recommended.
Please consider supporting the SauceNAO team as well by upgrading your plan.
With a free plan, you can request up to 200 posts in 24h.

For local machine learning tagging, posts can be tagged with one of [SmilingWolf's WD taggers](https://huggingface.co/SmilingWolf). Install the `wd-tagger` extra (`pip install "szurubooru-toolkit[wd-tagger]"`) and set `wd_tagger = true` in the `[auto_tagger]` section to use it.
The model set in `wd_tagger_model` (default: [SmilingWolf/wd-eva02-large-tagger-v3](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3), ~1.2GB) gets downloaded automatically from Hugging Face on first use and is cached locally afterwards. Any of the WD v3/v2 taggers work, e.g. `SmilingWolf/wd-swinv2-tagger-v3` or `SmilingWolf/wd-vit-tagger-v3` for smaller and faster models.
General tags and character tags use separate confidence thresholds (`wd_tagger_threshold` and `wd_tagger_character_threshold`), since character predictions are usually either confident or wrong. Use `szuru-toolkit preview-tags <file-or-post-id>` to see all scores near the thresholds when tuning them, and `szuru-toolkit auto-tagger --dry-run <query>` to preview which tags a run would change without updating any post.

With `wd_tagger_review = true`, posts whose best character score lands between `wd_tagger_review_threshold` and `wd_tagger_character_threshold` get tagged `needs_review` — a szurubooru query for exactly the ambiguous character matches worth curating manually.

Videos are tagged as well if ffmpeg is installed (`wd_tagger_videos`): frames are sampled across the duration — longer videos get more frames — and their scores averaged, so tags that only appear in a single frame don't stick.

Inference runs on the CPU by default. For hardware acceleration, set `wd_tagger_providers` in `config.toml`, e.g. `["CoreMLExecutionProvider"]` on Apple Silicon or `["CUDAExecutionProvider"]` on NVIDIA GPUs (requires the `onnxruntime-gpu` package). Unavailable providers fall back to the CPU.

## :page_with_curl: Commands
The CLI is installed as `szuru-toolkit` and under the shorter alias `szuructl` — both are identical.

Following commands are currently available:

* `auto-tagger`: Tag posts automatically
* `create-relations`: Create relations between character and parody tag categories
* `create-tags`: Create tags based on a tag file or query
* `delete-posts`: Delete posts
* `find-duplicates`: Find visually duplicate posts via perceptual hashing
* `fix-relations`: Complete post relation sets so every member of a set references all other members
* `import-from-booru`: Download and tag posts from various Boorus
* `import-from-url`: Batch importing of URLs based on [gallery-dl](https://github.com/mikf/gallery-dl)
* `preview-tags`: Show WD tagger scores near the thresholds for a file or post without tagging anything
* `reset-posts`: Remove tags and sources
* `tag-posts`: Tag posts manually
* `upload-media`: Upload media files
* `webserver`: Run the webserver for the browser extensions

Check `szuru-toolkit -h` or `szuru-toolkit COMMAND -h` for a detailed description of supported options.

If you cloned the repo from GitHub, prefix the above scripts with `uv run`, e.g. `uv run szuru-toolkit auto-tagger "date:today"`. Note that your current working directory has to be the root of the GitHub project.

If your query starts with a dash (`-`), for example to negate a tag, you have to separate the query from the command with two dashes (This doesn't work with uv run):

`szuru-toolkit auto-tagger --no-wd-tagger -- "-foo bar"`

While most commands are self explanatory, the following require a bit of extra attention:

### :label: create-relations
__Examples__
* `szuru-toolkit create-relations hitori_bocchi`
  * Will create the implication _bocchi_the_rock_ for tag _hitori_bocchi_ if other posts are found with query _hitori_bocchi_ containing _bocchi_the_rock_ as the parody (tag has to be of category _series_ or _parody_)
  * Will also add _hitori_bocchi_ as a suggestion to the parody tag _bocchi_the_rock_
  * These relations will only get generated if at least X posts are found containing the tags _bocchi_the_rock_ and _hitori_bocchi_. Control X with `threshold` under `[create_relations]` in `config.toml`.

### :label: create-tags
If no `tag_file` is specified, the script will download the most recent 100 tags from Danbooru which have been used at least ten times.

You can use tools like [Grabber](https://github.com/Bionus/imgbrd-grabber) to download a tag list from common boorus.

The `tag_file` has to be in following format:

```
<tag_a>,<category_name>
<tag_b>,<category_name>
<tag_..n>,<category_name>
```

The category has to be created beforehand manually (e.g. default, artist, parody/series, character and meta).

__Examples__
* `szuru-toolkit create-tags`
* `szuru-toolkit create-tags --query genshin* --overwrite`
* `szuru-toolkit create-tags --tag-file tags.txt`

### :link:	import-from-url
This scripts imports posts with their tags from the URL passed to this script.
In the background, it simply calls the [gallery-dl](https://github.com/mikf/gallery-dl) script and parses its output.
Alternatively, an input file with multiple URLs can be specified.

It's recommended to use the `--cookies` flag for authentication, check https://github.com/mikf/gallery-dl#cookies for details.

Posts imported from e-hentai/exhentai get the gallery URL set as their source and the `artist:` tag from the gallery applied; the namespaced e-hentai tags themselves are not imported.

__Examples__
* `szuru-toolkit import-from-url "https://danbooru.donmai.us/posts?tags=foo"`
* `szuru-toolkit import-from-url "https://chan.sankakucomplex.com/?tags=foo"`
* `szuru-toolkit import-from-url "https://beta.sankakucomplex.com/post/show/<id>"`
* `szuru-toolkit import-from-url "https://e-hentai.org/g/<gid>/<token>/"`
* `szuru-toolkit import-from-url --cookies "~/cookies.txt" --range ":100" "https://twitter.com/<USERNAME>/likes"`
* `szuru-toolkit import-from-url --input-file urls.txt "https://danbooru.donmai.us/posts?tags=foo" "https://beta.sankakucomplex.com/post/show/<id>"`

## :information_source:	Image credit
GitHub repo icon: <a href="https://www.flaticon.com/free-icons/code" title="code icons">Code icons created by Smashicons - Flaticon</a>
