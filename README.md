<p align="center">
<img src="https://cdn-icons-png.flaticon.com/512/2581/2581053.png"
  alt="szurubooru-toolkit icon"
  width="128" height="128">
</p>

# szurubooru-toolkit
Python package and script collection to manage your [szurubooru](https://github.com/rr-/szurubooru) image board.

## :ballot_box_with_check: Requirements
In order to run the included scripts, a Python release `>=3.8` and the configuratrion file `config.toml` is required.

The `config.toml` file needs to be always present in your current working directory from where you are executing the scripts.
You can find a sample config file in the [GitHub repository](https://github.com/reluce/szurubooru-toolkit) of this package.

## :hammer_and_wrench: Installation
This package is available on [PyPI](https://pypi.org/project/szurubooru-toolkit/) and can be installed with pip:
`pip install szurubooru-toolkit`

Alternatively, you can clone the package from GitHub and set everything up with [Poetry](https://python-poetry.org/docs/). In the root directory of this repository, execute `poetry install`.

Please note this package requires Tensorflow for Deepbooru tagging and other required packages which do take up quite a lot of disk space (>400MB).
A future release of this package will offer an option without the need to install Tensorflow if you don't want to use Deepbooru tagging.

### Docker Instructions
If you would like to run the toolkit in a Docker container instead, follow the
instructions below.

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
1. If you would like to use deepbooru or tag files, create `misc/deepbooru`
   and/or `misc/tags` in the same location and follow the instructions linked
   below
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
   auto-tagger`, replacing `container_name` with the container name.
1. If you would like the container to run a one-time command and then quit with
   `docker-compose.yml`, add a `command` configuration [like
   this](https://docs.docker.com/compose/compose-file/compose-file-v3/#command).

## :memo: User configuration
Make your changes in the `config_sample.toml` file provided in the git repo and rename it to `config.toml` afterwards.

Note that path names have to be specified with forward slashes (/) if you're using Windows.

<details>
  <summary>:information_source: config.toml reference</summary>

| Section | Option | Description | Examples/Default |
|---------|--------|-------------|-----------------|
| `szurubooru` | `url` | The URL of your szurubooru | `"https://szuru.example.com"` |
| `szurubooru` | `username` | Username which connects to the szuruboori API | `"my_szuru_user"` |
| `szurubooru` | `api_token` | API token of `username`. Generate one in szurubooru from _Account_ > _Login tokens_ > _Create token_ | `"my_api_token"` |
| `szurubooru` | `public` | If your szurubooru is reachable over the internet | `false` |
| `auto_tagger` | `saucenao_api_token` | In case you want to increase your daily query limit | `"my_saucenao_api_token"` |
| `auto_tagger` | `saucenao_enabled` | Set this to `false` and `deepbooru_enabled` to `true` if you only want to tag with Deepbooru | `true` |
| `auto_tagger` | `deepbooru_enabled` | If enabled, tag the post with Deepbooru if no tags with SauceNAO were found | `false` |
| `auto_tagger` | `deepbooru_model` | Path to the Deepbooru model | `"./misc/deepbooru/model-resnet_custom_v3.h5"` |
| `auto_tagger` | `deepbooru_threshold` | Define how accurate the matched tag from Deepbooru has to be | `"0.7"` |
| `auto_tagger` | `deepbooru_forced` | Always tag with SauceNAO and Deepbooru | `false` |
| `auto_tagger` | `deepbooru_set_tag` | Tag Deepbooru post with tag `deepbooru` | `true` |
| `auto_tagger` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `auto_tagger` | `use_pixiv_artist` | If the artist could only be found on pixiv, create and use the pixiv artist. Category has to be 'artist'. | `false` |
| `danbooru` | `user` | Danbooru user | `"None"` |
| `danbooru` | `api_key` | Danbooru api key | `"None"` |
| `gelbooru` | `user` | Gelbooru user | `"None"` |
| `gelbooru` | `api_key` | Gelbooru api key | `"None"` |
| `konachan` | `user` | Konachan user | `"None"` |
| `konachan` | `password` | Konachan password | `"None"` |
| `yandere` | `user` | Yandere user | `"None"` |
| `yandere` | `password` | Yandere password | `"None"` |
| `sankaku` | `user` | Sankaku user | `"None"` |
| `sankaku` | `password` | Sankaku password | `"None"` |
| `pixiv` | `user` | Pixiv user. Currently not being used. | `"None"` |
| `pixiv` | `password` | Pixiv password. Currently not being used. | `"None"` |
| `pixiv` | `token` | Pixiv token. Currently not being used. | `"None"` |
| `twitter` | `user_id` | The user id which should be queried. | `"None"` |
| `twitter` | `consumer_key` | See https://developer.twitter.com/en/docs/authentication/oauth-1-0a | `"None"` |
| `twitter` | `consumer_secret` | See https://developer.twitter.com/en/docs/authentication/oauth-1-0a | `"None"` |
| `twitter` | `access_token` | See https://developer.twitter.com/en/docs/authentication/oauth-1-0a | `"None"` |
| `twitter` | `access_token_secret` | See https://developer.twitter.com/en/docs/authentication/oauth-1-0a | `"None"` |
| `upload_media` | `src_path` | Every valid media file under this dir (recursively) will get uploaded | `"/local/path/to/upload/dir"` |
| `upload_media` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `upload_media` | `cleanup` | Set this to true if images in the `src_path` should be deleted after upload | `false` |
| `upload_media` | `tags` | These tags will get set for all uploaded posts. Separate them by a comma. | `["tagme", "tag1", "tag2", "tagN"]` |
| `upload_media` | `auto_tag` | Set this to true if you want your post to be automatically tagged after upload | `false` |
| `upload_media` | `max_similarity` | Adjust this value to ignore posts if a similar post higher than the threshold has already been uploaded. 1.00 being basically the same image, but not necessarily. Set to 1.00 if you know there are not duplicates. | `"0.99"` |
| `upload_media` | `convert_to_jpg` | Convert images to JPG to save disk space. This won't overwrite the source files and only affects the uploaded image. Images might slip through identical post check. | `false` |
| `upload_media` | `convert_quality` | Only images above this threshold will be converted to jpg if `convert_to_jpg` is True. | `"3MB\|500KB"` |
| `upload_media` | `shrink` | Set to true to shrink images to shrink_dimensions based on shrink_threshold below. Images might slip through identical post check. | `false` |
| `upload_media` | `shrink_threshold` | Images which total pixel size exceeds this treshold will be resized to `shrink_size`. E.g. 2000x3000 results in 6000000. | `"6000000"` |
| `upload_media` | `shrink_dimensions` | Set the max value for width/height. Keeps aspect ratio. E.g. 2000x4000 results in 700x1400, 4000x2000 in 1400x700 (with `"1400x1400"`). | `"2500x2500"` |
| `upload_media` | `default_safety` | # Set the default safety in case neither SauceNAO, nor Deepbooru could determine it | `safe` |
| `import_from_booru` | `deepbooru_enabled` | Apply Deepbooru tagging additionally besides fetched tags from Booru | `false` |
| `import_from_booru` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `import_from_url` | `tmp_path` | Path to directory where temporary downloads from gallery-dl script will be saved | `false` |
| `import_from_url` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `import_from_twitter` | `saucenao_enabled` | Tag posts with SauceNAO | `false` |
| `import_from_twitter` | `deepbooru_enabled` | Tag posts with Deepbooru | `false` |
| `import_from_twitter` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `create_tags` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `delete_posts` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `reset_posts` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `tag_posts` | `hide_progress` | Set this to true to hide the progress bar | `false` |
| `logging` | `log_enabled` | If logging to a log file should be enabled | `false` |
| `logging` | `log_file` | Specify the path of the log file | `"C:/Users/Foo/Desktop/szurubooru_toolkit.log"` |
| `logging` | `log_level` | Specify the log level. `DEBUG` logs the most information | `"DEBUG"\|"INFO"\|"WARNING"\|"ERROR"\|"CRITICAL"` |
| `logging` | `log_colorized` | If the log file should be colorized. Requires compatible viewer (e.g. `less -r <log_file>`). | `true` |
</details>

Creating a SauceNAO account and an API key is recommended.
Please consider supporting the SauceNAO team as well by upgrading your plan.
With a free plan, you can request up to 200 posts in 24h.

For Deepbooru support, download the current release [here](https://github.com/KichangKim/DeepDanbooru/releases/tag/v3-20211112-sgd-e28) (v3-20211112-sgd-e28) and extract the contents of the zip file. Specify the path of the folder with the extracted files in `deepbooru_model`.
Please note that you have to set `deepbooru_enabled` if you want to use it.

## :page_with_curl: Scripts
Following scripts are currently available:

* `auto-tagger`: Batch tagging of posts with SauceNAO and Deepbooru
* `create-relations`: Create relations between character and parody tag categories
* `create-tags`: Batch creation of tags with their categories
* `delete-posts`: Batch delete of posts
* `import-from-booru`: Batch importing of posts with their tags from various Boorus
* `import-from-twitter`: Batch importing of Twitter favorites
* `import-from-url`: Batch importing of URLs based on [gallery-dl](https://github.com/mikf/gallery-dl)
* `reset-posts`: Batch resetting of posts (remove tags and sources)
* `upload-media`: Batch upload of media files from local source folder
* `tag-posts`: Manual batch tagging

See the descriptions below on how to use them.

If you installed this package with pip, you can generally just call the scripts from your shell (if your $PATH is set correctly).

If you cloned the repo from GitHub, prefix the above scripts with `poetry run`, e.g. `poetry run auto-tagger "date:today"`. Note that your current working directory has to be the the root of the GitHub project.

### :gear: auto-tagger
This script accepts a szurubooru query as a user input, fetches all posts returned by it and attempts to tag it using SauceNAO/Deepbooru.

If no matches from SauceNAO were found, the script keeps the previously set tags of the post and additionally appends the tag `tagme`.

You can set `deepbooru_enabled` to `true` in your config.toml file. In that case, the script falls back to tag posts with the supplied Deepbooru model.
If you only want to use Deepbooru, set `deepbooru_enabled` to `true` and `saucenao_enabled` to `false`. If you want to use SauceNAO and Deepbooru, set following options to `true`: `saucenao_enabled`, `deepbooru_enabled` and `deepbooru_forced`.

__Usage__
```
usage: auto-tagger [-h] [--add-tags ADD_TAGS] [--remove-tags REMOVE_TAGS] query

This script will automagically tag your szurubooru posts based on your input query.

positional arguments:
  query                 Specify a single post id to tag or a szuru query. E.g. "date:today tag-count:0"

options:
  -h, --help            show this help message and exit
  --add-tags ADD_TAGS   Specify tags, separated by a comma, which will be added to all posts matching your query.
  --remove-tags REMOVE_TAGS
                        Specify tags, separated by a comma, which will be removed from all posts matching your query.
```

__Examples__
* `auto-tagger "date:today tag-count:0"`
* `auto-tagger "date:2021-04-07"`
* `auto-tagger "tagme"`
* `auto-tagger "id:100..111"`
* `auto-tagger "id:100,101"`
* `auto-tagger --add-tags "foo,bar" --remove-tags "baz" "tagme"`

If we want to tag a single post, we can omit the keyword `id` in our query:

* `auto-tagger 100`

Alternatively, we can tag a single post and specify `--sankaku_url` to fetch the tags from the supplied URL (_untested with current release_):

`auto-tagger --sankaku_url https://chan.sankakucomplex.com/post/show/<id> 100`

This is especially useful since Sankaku has changed their API and aggregator sites like SauceNAO don't have the latest results there.

### :arrow_lower_right:	import-from-booru
This scripts imports posts and their tags from various Boorus that matched your input query.

In the `config.toml` file, you can set if the post should be additionally tagged with Deepbooru and if the progress bar should be shown.
Since this script is using the `upload-media` script to upload the post, following settings apply from the `upload-media` section:
* max_similarity
* convert_to_jpg
* convert_threshold
* shrink
* shrink_threshold
* shrink_dimensions

__Usage__
```
usage: import-from-booru [-h] [--limit LIMIT] {danbooru,gelbooru,konachan,yandere,all} query

This script downloads and tags posts from various Boorus based on your input query.

positional arguments:
  {danbooru,gelbooru,konachan,yandere,all}
                        Specify the Booru which you want to query. Use all to query all Boorus.
  query                 The search query for the posts you want to download and tag

optional arguments:
  -h, --help            show this help message and exit
  --limit LIMIT         Limit the search results to be returned (default: 100)
```

__Examples__
* `import-from-booru danbooru "tag1 tagN"`
* `import-from-booru yandere "tag1 tag2 -tagN"`
* `import-from-booru all "tag1 -tagN"`

Note that if you specify `all` to download from all Boorus, you are limited to two tags because free Danbooru accounts are limited to two tags per query.
If you have a Gold/Platinum account, set your credentials in `config.toml`. Note that it's currently untested if the script will work with upgraded accounts.

### :link:	import-from-url
This scripts imports posts with their tags from the URL passed to this script.
In the background, it simply calls the [gallery-dl](https://github.com/mikf/gallery-dl) script and parses its output.
Alternatively, an input file with multiple URLs can be specified.

In the `config.toml` file, you have to specify a directory where posts will be temporarily saved to.
Since this script is using the `upload-media` script to upload the post, following settings apply from the `upload-media` section:
* max_similarity
* convert_to_jpg
* convert_threshold
* shrink
* shrink_threshold
* shrink_dimensions

:information_source:️ **The source URL will be generated for following sites:**
* Gelbooru
* Danbooru
* E-Hentai
* Konachan
* Kemono
* Sankaku
* Yandere

Credentials in your `config.toml` file will be passed to the gallery-dl script if you use a single input URL to this script.

However, it's recommended to use the `--cookie` flag for authentication, check https://github.com/mikf/gallery-dl#cookies for details.

__Usage__
```
usage: import-from-url [-h] [--range RANGE] [--input-file INPUT_FILE] [--cookies COOKIES] [urls ...]

This script downloads and tags posts from various Boorus based on your input query.

positional arguments:
  urls                  One or multiple URLs to the posts you want to download and tag

options:
  -h, --help            show this help message and exit
  --range RANGE         Index range(s) specifying which files to download. These can be either a constant value, range, or slice (e.g. '5', '8-20', or '1:24:3')
  --input-file INPUT_FILE
                        Download URLs found in FILE.
  --cookies COOKIES     Path to a cookies file for gallery-dl to consume. Used for authentication.
```

__Examples__
* `import-from-url "https://danbooru.donmai.us/posts?tags=foo"`
* `import-from-url "https://chan.sankakucomplex.com/?tags=foo"`
* `import-from-url "https://beta.sankakucomplex.com/post/show/<id>"`
* `import-from-url --cookies "~/cookies.txt" --range ":100" ""https://twitter.com/<USERNAME>/likes"`
* `import-from-url --input-file urls.txt "https://danbooru.donmai.us/posts?tags=foo" "https://beta.sankakucomplex.com/post/show/<id>"`

### :dove: import-from-twitter (Deprecated)
This script fetches media files from your Twitter likes, uploads and optionally tags them.

:warning: __This script is deprecated. Use `import-from-url` instead.__

:warning: __OAuth 1.0a credentials are required to read the likes from a user. See https://developer.twitter.com/en/docs/authentication/oauth-1-0a on how to generate them.__

The `user_id` can be converted on sites like https://tweeterid.com/. If you configured above credentials, you can also get your own ID from the `access_token`, which is in following format: `<user_id>-<random_string>`

In the `config.toml` file, you can set if the post should be additionally tagged with SauceNAO or Deepbooru and if the progress bar should be shown.
Since this script is using the `upload-media` script to upload the post, following settings apply from the `upload-media` section:
* max_similarity
* convert_to_jpg
* convert_threshold
* shrink
* shrink_threshold
* shrink_dimensions

__Usage__
```
usage: import-from-twitter [-h] [--limit LIMIT] [--user-id USER_ID]

This script fetches media files from your Twitter likes, uploads and optionally tags them.

optional arguments:
  -h, --help         show this help message and exit
  --limit LIMIT      Limit the amount of Twitter posts returned (default: 25)
  --user-id USER_ID  Fetch likes from the specified user id
```

__Examples__
* `import-from-twitter --limit 50`
* `import-from-twitter --limit 50 --user_id 123`

### :arrow_upper_right: upload-media
This script searches through your specified upload folder in the `config.toml` file for any image/video files and uploads them to your szurubooru.

__Usage__

* `upload-media`

### :label: tag-posts
__Usage__
```
usage: tag-posts [-h] [--add-tags ADD_TAGS] [--remove-tags REMOVE_TAGS] [--mode {append,overwrite}] query

This script will tag your szurubooru posts based on your input arguments and mode.

positional arguments:
  query                 The search query for the posts you want to tag

optional arguments:
  -h, --help            show this help message and exit
  --add-tags ADD_TAGS   Specify tags, separated by a comma, which will be added to all posts matching your query.
  --remove-tags REMOVE_TAGS
                        Specify tags, separated by a comma, which will be removed from all posts matching your query.
  --mode {append,overwrite}
                        Set mode to overwrite to remove already set tags, set append to keep them (default: append).
  --update-implications
                        Fetches all tags from the posts matching the query and updates them if tag implications are missing (default: False)
```

__Examples__
* `tag-posts --add-tags "foo,bar" "date:2021-04-07"`
* `tag-posts --add-tags "foo,bar" --mode "overwrite" "foo bar"`
* `tag-posts --add-tags "foo,bar" --remove-tags "baz" "foo"`

### :arrows_counterclockwise: reset-posts
__Usage__
```
usage: reset-posts [-h] [--except-ids EXCEPT_IDS] [--add-tags ADD_TAGS] query

This script will remove tags and sources from your szurubooru posts based on your input search query.

positional arguments:
  query                 The search query for the posts you want to reset.

optional arguments:
  -h, --help            show this help message and exit
  --except-ids EXCEPT_IDS
                        Specify the post ids, separated by a comma, which should not be reset. Example: --except-ids "3,4,5"
  --add-tags ADD_TAGS   Specify tags, separated by a comma, which will be added to all posts matching your query after resetting.
```

__Examples__
* `reset-posts "foobar"`
* `reset-posts --add-tags "tagme" "foobar"`
* `reset-posts --add-tags "tagme,foo" "foobar"`
* `reset-posts --except-ids "2,4" --add-tags "tagme,foo" "foobar"`

### :wastebasket:	delete-posts
__Usage__
```
usage: delete-posts [-h] [--except-ids EXCEPT_IDS] query

This script will delete your szurubooru posts based on your input search query.

positional arguments:
  query                 The search query for the posts you want to delete.

optional arguments:
  -h, --help            show this help message and exit
  --except-ids EXCEPT_IDS
                        Specify the post ids, separated by a comma, which should not be deleted. Example: --except-ids "3,4,5
```

__Examples__
* `delete-posts "id:10,11,100,23"`
* `delete-posts --except-ids "12,23,44" "id:10..50"`

### :label: create-tags
__Usage__
```
usage: create-tags [-h] [--tag-file TAG_FILE] [--query QUERY] [--min-post-count MIN_POST_COUNT] [--limit LIMIT] [--overwrite]

This script will read the tags from specified file and create them in your szurubooru.

optional arguments:
  -h, --help            show this help message and exit
  --tag-file TAG_FILE   Specify the local path to the file containing the tags and categories. If specified, ignores other arguments.
  --query QUERY         Search for specific tags (default: "*").
  --min-post-count MIN_POST_COUNT
                        The minimum amount of posts the tag should have been used in (default: 10).
  --limit LIMIT         The amount of tags that should be downloaded. Start from the most recent ones (default: 100).
  --overwrite           Overwrite tag category if the tag already exists.
```

If no `tag_file` is specified, the script will download the most recent 100 tags from Danbooru which have been used at least ten times.

You can use tools like [Grabber](https://github.com/Bionus/imgbrd-grabber) to download a tag list from common boorus.

The `tag_file` has to be in following format:

```
<tag_a>,<category_name>
<tag_b>,<category_name>
<tag_..n>,<category_name>
```

The category has to be created beforehand manually (e.g. default, artist, series, character and meta).

__Examples__
* `create-tags`
* `create-tags --query genshin* --overwrite`
* `create-tags --tag-file tags.txt`

### :label: create-relations
__Usage__
```
usage: create-relations [-h] [--hide-progress HIDE_PROGRESS] query

Create relations between character and parody tag categories

positional arguments:
  query                 Search for specific tags (default: "*").

options:
  -h, --help            show this help message and exit
  --hide-progress HIDE_PROGRESS
                        Hide the progress bar.
```

__Examples__
* `create-relations hitori_bocchi`
  * Will create the implication _bocchi_the_rock_ for tag _hitori_bocchi_ if other posts are found with query _hitori_bocchi_ containing _bocchi_the_rock_ as the parody (tag has to be of category _series_ or _parody_)
  * Will also add _hitori_bocchi_ as a suggestion to the parody tag _bocchi_the_rock_
  * These relations will only get generated if at least X posts are found containing the tags _bocchi_the_rock_ and _hitori_bocchi_. Control X with `threshold` under `[create-relations]` in `config.toml`.

## :information_source:	Image credit
GitHub repo icon: <a href="https://www.flaticon.com/free-icons/code" title="code icons">Code icons created by Smashicons - Flaticon</a>
