from tqdm import tqdm
from time import sleep
from classes.api import API
from classes.iqdb import IQDB
from classes.boorus.danbooru import Danbooru
from saucenao_api import SauceNao
from classes.user_input import UserInput
from misc.helpers import get_metadata_sankaku, statistics, convert_rating

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
    sauce    = SauceNao(api_key=user_input.saucenao_api_key)
    danbooru = Danbooru(
        danbooru_user    = user_input.danbooru_user,
        danbooru_api_key = user_input.danbooru_api_key,
    )

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
            else:
                print('Can only tag a single post if you specify --sankaku_url.')
        else:
            for post_id in tqdm(post_ids, ncols=80, position=0, leave=False):
                post = api.get_post(post_id, local_temp_path=user_input.local_temp_path)

                if any(extension in post.image_url for extension in blacklist_extensions):
                    post.tags = ['tagme']
                else:
                    result_url = None
                    if not danbooru.get_by_md5(post.md5sum):
                        sauce_results = sauce.from_file(post.image)
                        for sauce_result in sauce_results:
                            if 'danbooru' in sauce_result.urls[0]:
                                result_url = sauce_result.urls[0]

                    if danbooru.result or result_url:
                        if result_url:
                            danbooru.get_result(result_url)
                            post.source = result_url
                        else:
                            post.source = danbooru.source
                        tags = danbooru.get_tags()
                        post.rating = convert_rating(danbooru.get_rating())
                        statistics(1, 0)
                    else:
                        tags = ['tagme']
                        statistics(0, 1)

                    if post.tags and 'tagme' in tags:
                        post.tags.append(tags[0])
                    else:
                        post.tags = tags

                # Set meta data for the post
                try:
                    api.set_meta_data(post)
                except Exception as e:
                    print(e)

                # Sleep 3 seconds so SauceNAO does not ban us
                sleep(3)

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
