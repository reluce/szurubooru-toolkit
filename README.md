# szurubooru-scripts
Simplify your file uploads and automatically tag your posts.

## Requirements

A python3 release and the required modules. Install those with:

`python3 -m pip install requirements.txt`

## User configuration
Make your changes to the supplied `config_sample.json` file and rename it to `config.json` afterwards.

If you want so specify multiple tags for your upload, separate each of the tags by a comma: ["tag1","tag2","tagN"]

We can generate our szuru API token with following command:
`echo -n username:token | base64`

Creating a SauceNAO account and an API key is recommended.
Please consider supporting the SauceNAO team as well by upgrading your plan.
With a free plan, you can request up to 200 posts in 24h.

For DeepBooru support, download the current release [here](https://github.com/KichangKim/DeepDanbooru/releases/tag/v3-20211112-sgd-e28) (v3-20211112-sgd-e28) and extract the contents of the zip file to misc/deepbooru.
If needed, change the variable `deepbooru_model` in your config to the path of the model.

## Scripts

### upload_images
This script searches through your specified upload folder in the config file for any image/video files and uploads them to your booru.
After the upload has been completed, the script attempts to delete empty directories under your upload directory.

#### Usage
After editing the config file, we can just execute the script:

`python3 upload_images.py`

### auto_tagger
This script accepts a szurubooru query as a user input, fetches all posts returned by it and attempts to tag it using SauceNAO.

If no matches from SauceNAO were found, the script keeps the previously set tags of the post and additionally appends the tag `tagme`.

You can set "deepbooru_enabled" to "True" in your config.json file. In that case, the script falls back to tag posts with the supplied DeepBooru model.

#### Usage
After editing and renaming the sample config file to config.json, we can just execute the script with our query:

* `python3 auto_tagger.py 'date:today tag-count:0'`
* `python3 auto_tagger.py 'date:2021-04-07'`
* `python3 auto_tagger.py 'tagme'`
* `python3 auto_tagger.py 'id:100,101'`

If we want to tag a single post, we can omit the keyword `id` in our query:

* `python3 auto_tagger.py 100`

Alternatively, we can tag a single post and specify `--sankaku_url` to fetch the tags from the supplied URL:

`python3 auto_tagger.py --sankaku_url https://chan.sankakucomplex.com/post/show/<id> 100`

This is especially useful since Sankaku has changed their API and aggregator sites like SauceNAO don't have the latest results there.

## ToDo's
* Handle user input better
* Better error handling, especially with said user input
* Add a reverse image search for Sankaku
* Probably a lot of refactoring
