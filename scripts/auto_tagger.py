from time import sleep

from classes.api import API
from classes.deepbooru import DeepBooru
from classes.saucenao import SauceNao
from classes.user_input import UserInput
from misc.helpers import audit_rating
from misc.helpers import collect_sources
from misc.helpers import collect_tags
from misc.helpers import get_metadata_sankaku
from misc.helpers import statistics
from tqdm import tqdm


def main():
    """
    Parse user input and get all post ids based on the input query.
    After that, start tagging either based on the sankaku_url if specified or IQDB.
    """

    user_input = UserInput()
    user_input.parse_config()
    user_input.parse_input()
    api = API(
        szuru_address=user_input.szuru_address,
        szuru_api_token=user_input.szuru_api_token,
        szuru_public=user_input.szuru_public,
    )
    saucenao = SauceNao(user_input)
    deepbooru = DeepBooru(user_input.deepbooru_model)

    # Get post ids and pages from input query
    post_ids, total = api.get_post_ids(user_input.query)
    blacklist_extensions = ['mp4', 'webm', 'mkv']

    # Fetch tags from Sankaku if --sankaku_url is supplied
    if user_input.sankaku_url:
        if user_input.query.isnumeric():
            post = api.get_post(post_ids[0])
            post.tags, post.rating = get_metadata_sankaku(user_input.sankaku_url)
            post.source = user_input.sankaku_url

            # Set meta data for the post
            try:
                api.set_meta_data(post)
                statistics(tagged=1)
            except Exception as e:
                statistics(untagged=1)
                print(f'Could not tag post with Sankaku: {e}')
        else:
            print('Can only tag a single post if you specify --sankaku_url.')
    # Otherwise begin to get tags from SauceNAO
    else:
        for post_id in tqdm(post_ids, ncols=80, position=0, leave=False, disable=user_input.tagger_progress):
            try:
                post = api.get_post(post_id)
            except Exception as e:
                print(f'Could not fetch post {post_id}: {e}')

            is_blacklisted = False
            for extension in blacklist_extensions:
                if extension in post.image_url:
                    is_blacklisted = True

            if is_blacklisted:
                statistics(skipped=1)
                continue

            if user_input.use_saucenao:
                tags, source, rating, limit_short, limit_long = saucenao.get_metadata(post)

                # Get previously set tags and add new tags
                final_tags = collect_tags(tags, post.tags)

                # Get previously set sources and add new sources
                list_source_scraped = source.splitlines()
                list_source_post = post.source.splitlines()
                post.source = collect_sources(*list_source_scraped, *list_source_post)

                post.rating = audit_rating(rating, post.rating)

                if len(tags) > 0:
                    statistics(tagged=1)

                if not limit_long == 0:
                    # Sleep 35 seconds after short limit has been reached
                    if limit_short == 0:
                        sleep(35)
                else:
                    print('Your daily SauceNAO limit has been reached. Consider upgrading your account.')
                    break
            else:
                final_tags = [post.tags]
                tags = []

            # Fallback to DeepBooru if no tags were found or use_saucenao is false
            if (not len(tags) or not user_input.use_saucenao) and user_input.deepbooru_enabled:
                post.source = 'DeepBooru'
                rating, tags = deepbooru.tag_image(user_input.local_temp_path, post.image_url, user_input.threshold)
                final_tags = final_tags + tags

                if rating is None:
                    post.rating = 'unsafe'

                if not tags and 'tagme' not in final_tags:
                    final_tags.append('tagme')
                    statistics(untagged=1)
                else:
                    statistics(deepbooru=1)
            elif not user_input.use_saucenao:
                print()
                print('Nothing to do. Enable either SauceNAO or DeepBooru in your config.')
                statistics(skipped=1)

            # If any tags were collected with SauceNAO or DeepBooru, tag the post
            if len(tags):
                if 'tagme' in final_tags:
                    final_tags.remove('tagme')
                post.tags = final_tags
                api.set_meta_data(post)

    total_tagged, total_deepbooru, total_untagged, total_skipped = statistics()

    print()
    print('Script has finished tagging.')
    print(f'Total:     {total}')
    print(f'Tagged:    {str(total_tagged)}')
    print(f'DeepBooru: {str(total_deepbooru)}')
    print(f'Untagged:  {str(total_untagged)}')
    print(f'Skipped:   {str(total_skipped)}')


if __name__ == '__main__':
    main()
