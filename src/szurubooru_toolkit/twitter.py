import re
from math import ceil

import tweepy
from loguru import logger


class Twitter:
    """Twitter API"""

    def __init__(self, consumer_key: str, consumer_secret: str, access_token: str, access_token_secret: str) -> None:
        """Initializes a Tweepy client object as `self.client` with user credentials.

        We will use OAuth 1.0a authentication.

        For more information, see https://developer.twitter.com/en/docs/authentication/oauth-1-0a.

        Args:
            consumer_key (str): See above link on how to generate one.
            consumer_secret (str): See above link on how to generate one.
            access_token (str): See above link on how to generate one.
            access_token_secret (str): See above link on how to generate one.
        """

        self.client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    def get_media_from_liked_tweets(self, user_id: int, limit: int = 25) -> list:
        """Retrieves media files from liked tweets from `user_id`.

        Args:
            user_id (int): The user_id which should be queried.
            limit (int): Limit the amount of tweets returned (default: 25).

        Returns:
            list: A list which contains the tweet URL and the associated media file URLs as a tuple.
        """

        def set_media_refs(data: list, tweets: list) -> None:
            """Appends a tuple of the Tweet url and their media ref links to a list.

            Args:
                data (list): The data list from the Twitter response.
                tweets (list): List where the tuples will get appended to.
            """
            for tweet in data:
                if tweet.attachments:
                    tweet_url = Twitter.get_tweet_url(tweet.entities['urls'])
                    media_refs = Twitter.get_media_refs(tweet.attachments['media_keys'], response.includes['media'])
                    tweets.append(tuple((tweet_url, media_refs)))

        if limit > 100:
            total_posts_to_fetch = limit
            limit = 100
        else:
            total_posts_to_fetch = None

        response = self.client.get_liked_tweets(
            user_id,
            user_auth=True,
            expansions=['attachments.media_keys'],
            tweet_fields=['entities'],
            media_fields=['url', 'variants'],
            max_results=limit,
        )

        tweets = []
        set_media_refs(response.data, tweets)

        # If user limit is > 100, start pagination.
        if total_posts_to_fetch:
            try:
                next_token = response.meta['next_token']
            except KeyError:
                next_token = False

            total_pages = ceil(total_posts_to_fetch / 100)
            page = 2  # We already retrieved page 1

            while next_token and page <= total_pages:
                # On the last page, retrieve only the last double digits posts from the limit.
                # 1230 -> 30, 123 -> 23
                # If last two digits are 0s, assume 100 and fetch the max amount of posts.
                if page == total_pages:
                    limit = int(str(total_posts_to_fetch)[-2:])
                    if limit == 0:
                        limit = 100

                response = self.client.get_liked_tweets(
                    user_id,
                    user_auth=True,
                    expansions=['attachments.media_keys'],
                    tweet_fields=['entities'],
                    media_fields=['url', 'variants'],
                    max_results=limit,
                    pagination_token=next_token,
                )

                try:
                    next_token = response.meta['next_token']
                except KeyError:  # In case we reached the last page
                    next_token = False

                page += 1
                set_media_refs(response.data, tweets)

        return tweets

    @staticmethod
    def get_tweet_url(entities_urls: dict) -> str:
        """Extract and return the tweets URL.

        Args:
            entities_urls (dict): The URL entities from a Tweepy tweet object.

        Returns:
            str: The tweet's URL.
        """

        for entity in entities_urls:
            if 'twitter.com' in entity['expanded_url']:
                twitter_url = entity['url']

        return twitter_url

    @staticmethod
    def get_media_refs(media_keys: list, media_list: list) -> list:
        """Match the tweets media attachments to the tweet itself.

        Since the media attachments are in a separete object from the tweet's data,
        we have to piece those two together.

        Args:
            media_keys (list): A list of media_keys from the tweet.
            media_list (list): A list of Tweepy media objects which contains the media_key for reference.

        Returns:
            list: A list with a dict which contains the media URL (up to 4096x4096 resolution)
                and the file's extension.
        """

        media_refs = []
        for media in media_list:
            if media.media_key in media_keys:
                if media.type in ['video', 'animated_gif']:
                    video_url = Twitter.get_highest_quality_video(media.data['variants'])
                    file_ext = Twitter.get_file_ext(video_url)
                    media_refs.append({'url': video_url, 'file_ext': file_ext})
                else:
                    file_ext = Twitter.get_file_ext(media.url)
                    media_refs.append({'url': media.url + '?name=4096x4096', 'file_ext': file_ext})

        return media_refs

    @staticmethod
    def get_file_ext(url: str) -> str:
        """Exctract and return the file extension.

        Args:
            url (str): The Twitter file URL.

        Returns:
            str: The file extension (without a dot).
        """

        try:
            file_ext = re.findall(r'\.mp4|\.png|\.jpg|\.gif|\.webm', url)[0].replace('.', '')
        except Exception as e:
            file_ext = None
            logger.debug(f'Could not extract file extension from "{url}": {e}')

        return file_ext

    @staticmethod
    def get_highest_quality_video(variants: list) -> str:
        """Return the highest quality video URL from a tweet.
        Can be applied to `media_type` `animated_gif` as well.

        Args:
            variants (list): The variants list of the Tweepy tweet object.

        Returns:
            str: Video URL with the highest quality match.
        """

        bit_rates = []

        for variant in variants:
            if 'bit_rate' in variant:
                bit_rates.append(variant['bit_rate'])

        highest_bitrate = max(bit_rates)
        for variant in variants:
            if 'bit_rate' in variant and variant['bit_rate'] == highest_bitrate:
                video_url = variant['url']

        return video_url
