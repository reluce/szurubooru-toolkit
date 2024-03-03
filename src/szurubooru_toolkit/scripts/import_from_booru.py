from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit.scripts import import_from_url


@logger.catch
def main(booru: str, query: str) -> None:
    """
    Retrieves and uploads posts from a specified booru based on user input.

    This script is building a list of URLs to pass to the import_from_url script.
    The import_from_url script is then called with the list of URLs.

    Args:
        booru (str): The name of the booru to retrieve posts from. Can be 'danbooru', 'gelbooru', 'konachan',
                      'sankaku', 'yandere', or 'all' to retrieve posts from all boorus.
        query (str): The search query to use when retrieving posts. Spaces in the query are replaced with '+'.

    Raises:
        KeyboardInterrupt: If the user interrupts the process, a message is logged and the program exits with status 1.
    """

    try:
        if config.import_from_booru['deepbooru']:
            config.upload_media['auto_tag'] = True
            config.auto_tagger['saucenao'] = False
            config.auto_tagger['deepbooru'] = True
        else:
            config.upload_media['auto_tag'] = False

        config.import_from_url['hide_progress'] = config.import_from_booru['hide_progress']
        config.import_from_url['tmp_path'] = config.import_from_booru['tmp_path']
        config.import_from_url['range'] = ':' + str(config.import_from_booru['limit'])
        query = query.replace(' ', '+')

        booru_url_mapping = {
            'danbooru': 'https://danbooru.donmai.us/posts?tags=',
            'gelbooru': 'https://gelbooru.com/index.php?page=post&s=list&tags=',
            'konachan': 'https://konachan.com/post?tags=',
            'sankaku': 'https://chan.sankakucomplex.com/?tags=',
            'yandere': 'https://yande.re/post?tags=',
        }

        if booru in booru_url_mapping:
            urls = [booru_url_mapping[booru] + query]
        elif booru == 'all':
            urls = [booru_url_mapping[booru] + query for booru in booru_url_mapping]

        import_from_url.main(urls)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
