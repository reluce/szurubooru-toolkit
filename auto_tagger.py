from tqdm import tqdm
from time import sleep
from classes.api import API
from classes.iqdb import IQDB
from classes.user_input import UserInput
from misc.helpers import get_metadata_sankaku, statistics

def get_iqdb_result(iqdb, post, booru_offline, local_temp_path):
    """
    Uploads your file to IQDB and returns the IQDB HTML result page.

    Args:
        iqdb: An IQDB object
        post: A post object
        booru_offline: If our booru is online or offline
        local_temp_path: Directory where images should be saved if booru is offline
    Returns:
        result_page: The IQDB HTML result page

    Raises:
        Exception
    """

    try:
        result_page = iqdb.get_result(post, booru_offline, local_temp_path)
        return(result_page)
    except Exception as e:
        print(e)
        print('Could not get results from IQDB.')

def parse_iqdb_result(iqdb, result_page, user_input):
    """
    Parses the IQDB HTML result page.

    Args:
        iqdb: An IQDB object
        result_page: The IQDB HTML result page
        user_input: A user input object

    Returns:
        tags: The tags of the post in a list
        source: The URL where meta data were fetched from
        rating: The rating of the post

    Raises:
        IndexError
    """

    tags   = ['tagme']
    source = 'Anonymous'
    rating = 'unsafe'

    try:
        tags = iqdb.get_tags(result_page, user_input.preferred_booru)
        if iqdb.results:
            source = iqdb.get_source(result_page, user_input.preferred_booru)
            rating = iqdb.get_rating()

            statistics(1, 0)
        else:
            statistics(0, 1)
    except IndexError:
        try:
            tags   = iqdb.get_tags(result_page, user_input.fallback_booru)
            source = iqdb.get_source(result_page, user_input.fallback_booru)
            rating = iqdb.get_rating()

            statistics(1, 0)
        except IndexError:
            try:
                source = iqdb.get_source(result_page)
                tags   = iqdb.get_tags_best_match(result_page, source)
                rating = iqdb.get_rating()

                statistics(1, 0)
            except IndexError:
                statistics(0, 1)
    
    return tags, source, rating

def main():
    """
    Parse user input and get all post ids based on the input query.
    After that, start tagging either based on the sankaku_url if specified or IQDB.
    """

    user_input = UserInput()
    user_input.parse_config()
    user_input.parse_input()
    api = API(
        booru_address   = user_input.booru_address,
        booru_api_token = user_input.booru_api_token,
        booru_offline   = user_input.booru_offline,
    )
    iqdb = IQDB()

    # Get post ids and pages from input query
    post_ids, total = api.get_post_ids(user_input.query)

    # If posts were found, start tagging
    if int(total) > 0:
        blacklist_extensions = ['mp4', 'webm', 'mkv']

        if user_input.sankaku_url:
            if user_input.query.isnumeric():
                post = api.get_post(post_ids[0])
                post.tags, post.rating = get_metadata_sankaku(user_input.sankaku_url) 
                post.source = user_input.sankaku_url

                # Set meta data for the post
                api.set_meta_data(post)
                statistics(1, 0)
            else:
                print('Can only tag a single post if you specify --sankaku_url.')
        else:
            for post_id in tqdm(post_ids, ncols=80, position=0, leave=False):
                post = api.get_post(post_id)

                if any(extension in post.image_url for extension in blacklist_extensions):
                    post.tags = ['tagme']
                else:
                    # Get post and upload it to iqdb
                    result_page = get_iqdb_result(iqdb, post, api.booru_offline, user_input.local_temp_path)

                    # Parse result from iqdb. Don't remove previously set tags.
                    tags, post.source, post.rating = parse_iqdb_result(iqdb, result_page, user_input)
                    if post.tags and 'tagme' in tags:
                        post.tags.append(tags[0])
                    else:
                        post.tags = tags

                # Set meta data for the post
                try:
                    api.set_meta_data(post)
                except Exception as e:
                    print(e)

                # Sleep 7 seconds so IQDB does not ban us
                sleep(7)

    total_tagged, total_untagged = statistics()
    skipped = int(total) - total_tagged - total_untagged
        
    print()
    print('Script has finished tagging.')
    print(f'Total:    {total}')
    print(f'Tagged:   {str(total_tagged)}')
    print(f'Untagged: {str(total_untagged)}')
    print(f'Skipped:  {str(skipped)}')

if __name__ == '__main__':
    main()
