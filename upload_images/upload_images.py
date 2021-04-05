import os
import json
import requests
import configparser
from glob import glob
from tqdm import tqdm
from requests.auth import HTTPBasicAuth

# Handle user config
config = configparser.ConfigParser()
config.read('config')

booru_address   = config['szurubooru']['address']
booru_api_url   = booru_address + '/api'
booru_api_token = config['szurubooru']['api_token']
booru_headers   = {'Accept': 'application/json', 'Authorization': 'Token ' + booru_api_token}
upload_dir      = config['options']['upload_dir']
tags            = config['options']['tags'].split(',')

def get_files(upload_dir):
    """
    Reads recursively images/videos from upload_dir.

    Args:
        upload_dir: The directory on the local system which contains the images/videos you want to upload

    Returns:
        files: A list which contains the full path of each found images/videos (includes subdirectories)
    """

    allowed_extensions = ['jpg', 'jpeg', 'png', 'mp4', 'webm', 'gif', 'svg']
    files_raw          = list(filter(None, [glob(upload_dir + '/**/*.' + extension, recursive = True) for extension in allowed_extensions]))
    files              = [y for x in files_raw for y in x]
    
    return files

def get_image_token(image):
    """
    Upload the image to the temporary uploads endpoint.
    We can access our temporary image with the image token.

    Args:
        image: The file object of the image
        file: The path to the file

    Returns:
        image_token: An image token from szurubooru

    Raises:
        Exception
    """

    post_url    = booru_api_url + '/uploads'

    try:
        response    = requests.post(post_url, files={'content': image}, headers=booru_headers)
        image_token = response.json()['token']

        return(image_token)
    except Exception as e:
        print(f'An error occured while getting the image token: {e}')

def check_similarity(image_token):
    """
    Do a reverse image search with the temporary uploaded image.

    Args:
        image_token: An image token from szurubooru
    
    Returns:
        exact_post: Includes meta data of the post if an exact match was found
        similar_posts: Includes a list with all similar posts

    Raises:
        Exception
    """

    post_url = booru_api_url + '/posts/reverse-search'
    metadata = json.dumps({'contentToken': image_token})
    
    try:
        response = requests.post(post_url, headers=booru_headers, data=metadata)
        exact_post = response.json()['exactPost']
        similar_posts = response.json()['similarPosts']

        return exact_post, similar_posts 
    except Exception as e:
        print(f'An error occured during the similarity check: {e}')

def upload_file(image_token, tags, similar_posts, file_path):
    """
    Uploads/Moves our temporary image to 'production' with similar posts if any were found.
    Deletes file after upload has been completed.

    Args:
        image_token: An image token from szurubooru
        similar_posts: Includes a list with all similar posts

    Raises:
        Exception
    """

    post_url = booru_api_url + '/posts'
    metadata = json.dumps({'tags': tags, 'safety': 'unsafe', 'relations': similar_posts, 'contentToken': image_token})

    try:
        res = requests.post(post_url, headers=booru_headers, data=metadata)
        #print(res.json())
        os.remove(file_path)
    except Exception as e:
        print(f'An error occured during the upload: {e}')
        

def delete_posts(start_id, finish_id):
    """
    If some posts unwanted posts were uploaded, you can delete those within the range of start_id to finish_id.

    Args:
        start_id: Start deleting from this post id
        finish_id: Stop deleting until this post id
    Raises:
        Exception
    """

    for id in range(start_id, finish_id + 1):
        post_url = booru_api_url + '/post/' + str(id)
        try:
            requests.delete(post_url, headers=booru_headers, data=json.dumps({'version': '1'}))
        except Exception as e:
            print(f'An error occured while deleting posts: {e}')

# Start processing the script from here on
files_to_upload  = get_files(upload_dir)

if files_to_upload:
    print('Found ' + str(len(files_to_upload)) + ' images. Starting upload...')

    for file_to_upload in tqdm(files_to_upload, ncols=80, position=0, leave=False):
        image = open(file_to_upload, 'rb')

        image_token = get_image_token(image)
        exact_post, similar_posts = check_similarity(image_token)

        if not exact_post:
            similar_posts_ids = []        
            for post in similar_posts:
                similar_posts_ids.append(post['post']['id'])
                
            upload_file(image_token, tags, similar_posts_ids, file_to_upload)

    print()
    print('Script has finished uploading.')
else:
    print('No images found to upload.')
