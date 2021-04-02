# szurubooru-scripts
Scripts which help managing larger szurubooru instances.

## upload_images
Specify your szurubooru URL, api key and the directory which contains your images you want to upload in the config file.
Note: Do not surround your data with quotes!

This script searches through your specified upload folder for any image/video files and uploads them to your booru.
While the script does delete the image after it has been uploaded, parent directories won't.
It is advised that you write your own clean up script which tailors your needs.
I included one that I use for myself.

## auto_tagger
WIP
