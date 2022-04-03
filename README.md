<p align="center">
<img src="https://cdn-icons-png.flaticon.com/512/2581/2581053.png"
  alt="szurubooru-toolkit icon"
  width="128" height="128">
</p>

# szurubooru-toolkit
Python package and script collection to manage your [szurubooru](https://github.com/rr-/szurubooru) image board.

## Requirements
In order to run the included scripts, a Python release `>=3.8` and the configuratrion file `config.toml` is required.

The `config.toml` file needs to be present in your current working directory.
You can find a sample config file in the [git repository](https://github.com/reluce/szurubooru-toolkit) of this package.

## Installation
This package is available on [PyPI](https://pypi.org/project/szurubooru-toolkit/) and can be installed with pip:
`pip install szurubooru-toolkit`

Alternatively, you can clone the package from GitHub and set everything up with [Poetry](https://python-poetry.org/docs/). In the root directory of this repository, execute `poetry install`.

Please note this package requires Tensorflow for Deepbooru tagging and other required packages which do take up quite a lot of disk space (>400MB).
A future release of this package will offer an option without the need to install Tensorflow if you don't want to use Deepbooru tagging.

## User configuration
Make your changes in the `config_sample.toml` file provided in the git repo and rename it to `config.toml` afterwards.

Note that path names have to be specified with forward slashes (/) if you're using Windows.

<details>
  <summary>config.toml reference</summary>

| Section | Option | Description | Examples/Default |
|---------|--------|-------------|-----------------|
| szurubooru | url | The URL of your szurubooru | `"https://szuru.example.com"` |
| szurubooru | username | Username which connects to the szuruboori API | `"my_szuru_user"` |
| szurubooru | api_token | API token of `username`. Generate one in szurubooru from _Account_ > _Login tokens_ > _Create token_ | `"my_api_token"` |
| szurubooru | public | If your szurubooru is reachable over the internet | `false` |
| auto_tagger | saucenao_api_token | In case you want to increase your daily query limit | `"my_saucenao_api_token"` |
| auto_tagger | saucenao_enabled | Set this to `false` and `deepbooru_enabled` to `true` if you only want to tag with Deepbooru | `true` |
| auto_tagger | deepbooru_enabled | If enabled, tag the post with Deepbooru if no tags with SauceNAO were found | `false` |
| auto_tagger | deepbooru_model | Path to the Deepbooru model | `"./misc/deepbooru/model-resnet_custom_v3.h5"` |
| auto_tagger | deepbooru_threshold | Define how accurate the matched tag from Deepbooru has to be | `"0.7"` |
| auto_tagger | deepbooru_forced | Always tag with SauceNAO and Deepbooru | `false` |
| auto_tagger | hide_progress | Set this to true to hide the progress bar | `false` |
| auto_tagger | tmp_path | Local path where media files get downloaded temporarily if you szurubooru is not public. | `/tmp`, `C:/Users/Foo/Desktop` |
| danbooru | user | Danbooru user | `"None"` |
| danbooru | api_key | Danbooru api key | `"None"` |
| gelbooru | user | Gelbooru user | `"None"` |
| gelbooru | api_ley | Gelbooru api key | `"None"` |
| konachan | user | Konachan user | `"None"` |
| konachan | password | Konachan password | `"None"` |
| yandere | user | Yandere user | `"None"` |
| yandere | password | Yandere password | `"None"` |
| pixiv | user | Pixiv user. Currently not being used. | `"None"` |
| pixiv | password | Pixiv password. Currently not being used. | `"None"` |
| pixiv | token | Pixiv token. Currently not being used. | `"None"` |
| upload_media | src_path | Every valid media file under this dir (recursively) will get uploaded | `"/local/path/to/upload/dir"` |
| upload_media | hide_progress | Set this to true to hide the progress bar | `false` |
| upload_media | cleanup | Set this to true if images in the `src_path` should be deleted after upload | `false` |
| upload_media | tags | These tags will get set for all uploaded posts. Separate them by a comma. | `["tagme", "tag1", "tag2", "tagN"]` |
| upload_media | auto_tag | Set this to true if you want your post to be automatically tagged after upload | `false` |
| logging | log_enabled | If logging to a log file should be enabled | `false` |
| logging | log_file | Specify the path of the log file | `"C:/Users/Foo/Desktop/szurubooru_toolkit.log"` |
| logging | log_level | Specify the log level. `DEBUG` logs the most information | `"DEBUG"\|"INFO"\|"WARNING"\|"ERROR"\|"CRITICAL"` |
| logging | log_colorized | If the log file should be colorized. Requires compatible viewer (e.g. `less -r <log_file>`). | `true` |
</details>

Creating a SauceNAO account and an API key is recommended.
Please consider supporting the SauceNAO team as well by upgrading your plan.
With a free plan, you can request up to 200 posts in 24h.

For Deepbooru support, download the current release [here](https://github.com/KichangKim/DeepDanbooru/releases/tag/v3-20211112-sgd-e28) (v3-20211112-sgd-e28) and extract the contents of the zip file. Specify the path of the folder with the extracted files in `deepbooru_model`.
Please note that you have to set `deepbooru_enabled` if you want to use it.

## Scripts

### auto-tagger
This script accepts a szurubooru query as a user input, fetches all posts returned by it and attempts to tag it using SauceNAO/Deepbooru.

If no matches from SauceNAO were found, the script keeps the previously set tags of the post and additionally appends the tag `tagme`.

You can set `deepbooru_enabled` to `true` in your config.toml file. In that case, the script falls back to tag posts with the supplied Deepbooru model.
If you only want to use Deepbooru, set `deepbooru_enabled` to `true` and `saucenao_enabled` to `false`. If you want to use SauceNAO and Deepbooru, set following options to `true`: `saucenao_enabled`, `deepbooru_enabled` and `deepbooru_forced`.

__Usage__

After editing and renaming the sample config file to config.toml, we can just execute the script with our query:

* `auto-tagger "date:today tag-count:0"`
* `auto-tagger "date:2021-04-07"`
* `auto-tagger "tagme"`
* `auto-tagger "id:100,101"`

If we want to tag a single post, we can omit the keyword `id` in our query:

* `auto-tagger 100`

Alternatively, we can tag a single post and specify `--sankaku_url` to fetch the tags from the supplied URL (_untested with current release_):

`auto-tagger --sankaku_url https://chan.sankakucomplex.com/post/show/<id> 100`

This is especially useful since Sankaku has changed their API and aggregator sites like SauceNAO don't have the latest results there.

If you cloned the repo from GitHub, prefix the above commands with `poetry run`, e.g. `poetry run auto-tagger "date:today"`. Note that your current working directory has to be the the root of the GitHub project.

### upload-media
This script searches through your specified upload folder in the config file for any image/video files and uploads them to your szurubooru.

__Usage__

After editing the config file, we can just execute the script.

If you installed it with pip, execute `upload-media`. Note that `config.toml` has to be in your current working directory.

If you cloned the repo from GitHub, execute `poetry run upload-media`. Note that your current working directory has to be the the root of the GitHub project.

### create-tags (Currently not working, WIP)
This script reads the file `./misc/tags/tags.txt`, parses its contents and creates the tags in your szurubooru.

If the tag already exists, it will get updated with your changes.

You can use tools like [Grabber](https://github.com/Bionus/imgbrd-grabber) to download a tag list from common boorus.

The file has to be in following format:

```
<tag_a>,<category_number>
<tag_b>,<category_number>
<tag_..n>,<category_number>
```

|Category|Number|
|---|---|
|default|0|
|artist|1|
|series|2|
|character|3|
|meta|4|

__Usage__

After editing the config file, we can just execute the script.

If you installed it with pip, execute `create-tags`. Note that `config.toml` has to be in your current working directory.

If you cloned the repo from GitHub, execute `poetry run create-tags`. Note that your current working directory has to be the the root of the GitHub project.

## Image credit
GitHub repo icon: <a href="https://www.flaticon.com/free-icons/code" title="code icons">Code icons created by Smashicons - Flaticon</a>
