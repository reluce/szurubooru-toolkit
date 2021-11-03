from tqdm import tqdm
from time import sleep
from classes.api import API
from classes.iqdb import IQDB
# from classes.boorus.danbooru import Danbooru
from classes.saucenao import SauceNao
from classes.user_input import UserInput
from misc.helpers import get_metadata_sankaku, statistics, convert_rating, audit_rating, collect_tags, collect_sources

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
    image_search_engine = SauceNao(
        local_temp_path=user_input.local_temp_path,
        api_key=user_input.saucenao_api_key
    )
    # danbooru = Danbooru(
    #     danbooru_user    = user_input.danbooru_user,
    #     danbooru_api_key = user_input.danbooru_api_key,
    # )

    # Get post ids and pages from input query
    post_ids, total = api.get_post_ids(user_input.query)
    post_ready = []
    blacklist_extensions = ['mp4', 'webm', 'mkv']

    # If posts were found, start tagging
    for post_id in tqdm(post_ids, ncols=80, position=0, leave=False):
        post = api.get_post_old(post_id)

        is_blacklisted = False
        for extension in blacklist_extensions:
            if extension in post.image_url:
                is_blacklisted = True

        if is_blacklisted:
            statistics(0, 1)
            continue

        tags, source, rating = image_search_engine.get_metadata(post.image_url)

        new_tags = collect_tags(
            tags,
            post.tags
        )
        if not len(new_tags):
            new_tags.append('tagme')

        list_source_scraped = source.splitlines()
        list_source_post = post.source.splitlines()
        new_source = collect_sources(
            *list_source_scraped,
            *list_source_post
        )

        new_rating = audit_rating(
            rating,
            post.rating
        )

        post.tags = new_tags
        post.source = new_source
        post.rating = new_rating

        post_ready.append(post)
        statistics(1, 0)

        # Sleep 5 seconds so SauceNAO does not ban us
        sleep(5)

    for p in post_ready:
        api.set_meta_data(post)

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
