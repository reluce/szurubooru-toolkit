import argparse
from time import sleep

from szuru_toolkit import Config
from szuru_toolkit import Deepbooru
from szuru_toolkit import SauceNao
from szuru_toolkit.sankaku import scrape_sankaku
from szuru_toolkit.utils import sanitize_tags
from szuru_toolkit.utils import statistics

import pyszuru
from tqdm import tqdm


def parse_args() -> tuple:
    """
    Parse the input args to the script auto_tagger.py and set the object attributes accordingly.
    """

    parser = argparse.ArgumentParser(
        description='This script will automagically tag your szurubooru posts based on your input query.',
    )

    parser.add_argument(
        '--sankaku_url',
        dest='sankaku_url',
        help='Fetch tags from specified Sankaku URL instead of searching IQDB.',
    )
    parser.add_argument(
        'query',
        help='Specify a single post id to tag or a szuru query. E.g. \'date:today tag-count:0\'',
    )

    args = parser.parse_args()

    sankaku_url = args.sankaku_url
    query = args.query

    return sankaku_url, query


def parse_saucenao_results(sauce: SauceNao, post, szuru_public: bool, tmp_path: str):
    tags, source, rating, limit_short, limit_long = sauce.get_metadata(post.content, szuru_public, tmp_path)

    # Get previously set sources and add new sources
    source = [source for source in list(set().union(source, post.source)) if source]

    if not limit_long == 0:
        # Sleep 35 seconds after short limit has been reached
        if limit_short == 0:
            sleep(35)
    else:
        print('Your daily SauceNAO limit has been reached. Consider upgrading your account.')

    return sanitize_tags(tags), source, rating


def parse_deepbooru_result(deepbooru: Deepbooru, tmp_path: str, post_url: str, threshold):
    return deepbooru.tag_image(tmp_path, post_url, threshold)


def create_tags(szuru, tags):
    for tag in tags:
        try:
            szuru.createTag(tag)
        except pyszuru.SzurubooruHTTPError:
            pass  # Tag already exists


def main() -> None:
    """Placeholder"""

    config = Config()

    if not config.auto_tagger['saucenao_enabled'] and not config.auto_tagger['deepbooru_enabled']:
        print('Nothing to do. Enable either SauceNAO or Deepbooru in your config.')
        exit()

    sankaku_url, query = parse_args()

    szuru = pyszuru.API(config.szurubooru['url'], config.szurubooru['username'], token=config.szurubooru['api_token'])
    sauce = SauceNao(config)
    deepbooru = Deepbooru(config.auto_tagger['deepbooru_model'])

    posts = szuru.search_post(query)

    if sankaku_url:
        if query.isnumeric():
            posts[0].tags, posts[0].rating = scrape_sankaku(sankaku_url)
            posts[0].source = sankaku_url

            try:
                posts[0].push()
                statistics(tagged=1)
            except Exception as e:
                statistics(untagged=1)
                print(f'Could not tag post with Sankaku: {e}')
        else:
            print('Can only tag a single post if you specify --sankaku_url.')
    else:
        for post in tqdm(posts, ncols=80, position=0, leave=False, disable=config.auto_tagger['hide_progress']):
            tags = []

            if config.auto_tagger['saucenao_enabled']:
                tags, post.source, post.safety = parse_saucenao_results(
                    sauce,
                    post,
                    config.szurubooru['public'],
                    config.auto_tagger['tmp_path'],
                )

                create_tags(szuru, tags)

                try:
                    post.tags = list(set().union(post.tags, tags))  # Keep already set tags
                    statistics(tagged=1)
                except pyszuru.SzurubooruHTTPError as e:
                    print(e)
                    statistics(untagged=1)

            # Fallback to Deepbooru if no tags were found or use_saucenao is false
            if (not tags or not config.auto_tagger['saucenao_enabled']) and config.auto_tagger['deepbooru_enabled']:
                tags, post.safety = parse_deepbooru_result(
                    deepbooru,
                    config.auto_tagger['tmp_path'],
                    post.content,
                    config.auto_tagger['deepbooru_threshold'],
                )
                create_tags(szuru, tags)

                try:
                    post.tags = list(set().union(post.tags, tags))  # Keep already set tags
                    statistics(tagged=1)
                except pyszuru.SzurubooruHTTPError as e:
                    print(e)
                    statistics(untagged=1)

                post.source = ['Deepbooru']
                statistics(deepbooru=1)
            elif not config.auto_tagger['saucenao_enabled']:
                statistics(untagged=1)

            # If any tags were collected with SauceNAO or Deepbooru, tag the post
            if tags:
                post.tags = [tag for tag in post.tags if not tag.primary_name == 'tagme']

                post.push()

    total_tagged, total_deepbooru, total_untagged = statistics()

    print()
    print('Script has finished tagging.')
    # print(f'Total:     {total}')
    print(f'Tagged:    {str(total_tagged)}')
    print(f'Deepbooru: {str(total_deepbooru)}')
    print(f'Untagged:  {str(total_untagged)}')


if __name__ == '__main__':
    main()
