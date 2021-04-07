# szurubooru-scripts
Scripts which help managing larger szurubooru instances.

## Requirements

A python3 release and the required modules. Install those with:

`python3 -m pip install requirements.txt`

## Scripts

### upload_images
This script searches through your specified upload folder in the config file for any image/video files and uploads them to your booru.
After the upload has been completed, the script attempts to delete empty directories under your upload directory.

After editing the config file, we can just execute the script:

`python3 upload_images.py`

### auto_tagger
This script accepts a szurubooru query as a user input, fetches all posts returned by it and attempts to tag it.
In your config you can specify your preferred booru and fallback booru where tags should be fetched from.
If your image was found on neither of those choices, the script attempts to fallback to the best match returned by IQDB.

By default the script searches Danbooru first, Sankaku after that and falls back to the best match.

So simply edit your config file and execute the script with your query:

* `python3 auto_tagger.py 'date:today tag-count:0'`
* `python3 auto_tagger.py 'date:2021-04-07'`
* `python3 auto_tagger.py 'tagme'`
* `python3 auto_tagger.py 'id:100,101'`

Alternatively, you can tag a single post and specify `--sankaku_url` to fetch the tags from the supplied URL:

`python3 auto_tagger.py --sankaku_url https://chan.sankakucomplex.com/post/show/<id> 'id:100'`

This is especially useful since IQDB hasn't updated their Sankaku database in over three years+ now.

## User configuration
The config file accepts following input:
```INI
[szurubooru]
address   = https://example.com
api_token = my_api_key
offline   = True

[options]
upload_dir      = /local/path/to/upload/dir
preferred_booru = sankaku
fallback_booru  = danbooru
tags            = tagme,tag1,tag2,tag3
```
Input should be formatted like the provided example, meaning:
* No quotes around strings
* Separate tags by comma with no whitespaces

You can generate your API token with following command:
`echo -n username:token | base64`

## ToDo's
* Handle user input better
* Better error handling, especially with said user input
* Add a reverse image search for Sankaku
* Probably a lot of refactoring
