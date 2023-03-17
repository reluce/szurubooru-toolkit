import argparse

from loguru import logger
from tqdm import tqdm
from tweepy import errors

from szurubooru_toolkit import Twitter
from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.scripts import upload_media
from szurubooru_toolkit.utils import download_media
from szurubooru_toolkit.utils import get_md5sum


def parse_args() -> tuple:
    """Parse the input args to the script import_from_twitter.py and set the object attributes accordingly."""

    parser = argparse.ArgumentParser(
        description='This script fetches media files from your Twitter likes, uploads and optionally tags them.',
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=25,
        help='Limit the amount of Twitter posts returned (default: 25)',
    )

    parser.add_argument(
        '--user-id',
        type=int,
        default=None,
        help='Fetch likes from the specified user id.',
    )

    args = parser.parse_args()
    limit = args.limit
    user_id = args.user_id

    return user_id, limit


@logger.catch
def main() -> None:
    """Call respective functions to retrieve and upload posts based on user input."""

    try:
        user_id, limit = parse_args()

        if not user_id:
            if config.twitter['user_id'] != 'None':
                user_id = config.twitter['user_id']
            else:
                logger.critical(
                    'No user id specified! Pass --user-id to the script or configure the user_id in config.toml.',
                )
                exit()

        if config.import_from_twitter['saucenao_enabled']:
            config.auto_tagger['saucenao_enabled'] = True
        else:
            config.auto_tagger['saucenao_enabled'] = False

        if config.import_from_twitter['deepbooru_enabled']:
            config.auto_tagger['deepbooru_enabled'] = True
        else:
            config.auto_tagger['deepbooru_forced'] = False
            config.auto_tagger['deepbooru_enabled'] = False

        if not config.import_from_twitter['saucenao_enabled'] and not config.import_from_twitter['deepbooru_enabled']:
            config.upload_media['auto_tag'] = False

        twitter = Twitter(
            config.twitter['consumer_key'],
            config.twitter['consumer_secret'],
            config.twitter['access_token'],
            config.twitter['access_token_secret'],
        )

        try:
            tweets = twitter.get_media_from_liked_tweets(user_id, limit)
        except errors.Unauthorized:
            logger.critical(
                'You\'re unauthorized to retrieve the user\'s tweets! User profile is probably private. '
                'Configure credentials in config.toml.',
            )
            exit()

        logger.info(f'Found {len(tweets)} tweets with media attachments. Start importing...')

        for tweet in tqdm(
            tweets,
            ncols=80,
            position=0,
            leave=False,
            total=len(tweets),
            disable=config.import_from_twitter['hide_progress'],
        ):
            files = []
            for media in tweet[1]:
                files.append(download_media(media['url']))

            for index, file in enumerate(files):
                # Check by md5 hash if file is already uploaded
                md5 = get_md5sum(file)
                result = szuru.get_posts(f'md5:{md5}')

                try:
                    next(result)
                    logger.debug(f'Skipping tweet, already exists: {tweet}')
                except StopIteration:
                    logger.debug(f'Importing tweet: {tweet}')

                    metadata = {'tags': ['tagme'], 'safety': 'unsafe', 'source': tweet[0]}
                    upload_media.main(file, tweet[1][index]['file_ext'], metadata)

        logger.success('Script finished importing!')
    except KeyboardInterrupt:
        print('')
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
