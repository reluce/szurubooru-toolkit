# szurubooru-scripts
Scripts which help managing larger szurubooru instances.

## upload_images
This script searches through your specified upload folder for any image/video files and uploads them to your booru.
After the upload has been completed, the script attempts to delete empty directories under your upload directory.

### User configuration
The config file accepts following input:
```
[szurubooru]
address   = https://example.com
api_token = my_api_key

[options]
upload_dir = /local/path/to/upload/dir
tags = tagme,tag1,tag2,tag3
```
Input should be formatted like the provided example, meaning:
* No quotes around strings
* Separate tags by comma with no whitespaces

## auto_tagger
WIP
