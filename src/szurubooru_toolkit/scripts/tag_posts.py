from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import collect_sources
from szurubooru_toolkit.utils import get_cached_implications
from szurubooru_toolkit.utils import run_concurrently


@logger.catch
def main(query: str, add_tags: list = [], remove_tags: list = [], source: str = '') -> None:
    """
    Retrieve the posts from input query, set post.tags based on mode and update them in szurubooru.

    Args:
        query (str): The query to use for retrieving posts.
        add_tags (list, optional): A list of tags to add to the posts. Defaults to [].
        remove_tags (list, optional): A list of tags to remove from the posts. Defaults to [].
        source (str, optional): The source of the posts. Defaults to ''.

    Returns:
        None
    """

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.tag_posts['hide_progress']

        mode = config.tag_posts['mode']
        update_implications = config.tag_posts['update_implications']
        logger.debug(f'update_implications = {str(update_implications)}')

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            if not config.tag_posts['silence_info']:
                logger.info(f'Found no posts for your query: {query}')
            exit()

        if not config.tag_posts['silence_info']:
            logger.info(f'Found {total_posts} posts. Start tagging...')

        def worker(post) -> None:
            if mode == 'append':
                if add_tags:
                    post.tags = list(set().union(post.tags, add_tags))
                if source:
                    post.source = collect_sources(post.source, source)
            elif mode == 'overwrite':
                if add_tags:
                    post.tags = add_tags
                if source:
                    post.source = source

            if remove_tags:
                post.tags = [tag for tag in post.tags if tag not in remove_tags]

            if update_implications:
                for tag in post.tags:
                    for implication in get_cached_implications(tag):
                        if implication not in post.tags:
                            post.tags.append(implication)

            szuru.update_post(post)

        workers = max(1, int(config.tag_posts['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), hide_progress)

        if not config.tag_posts['silence_info']:
            logger.success('Finished tagging!')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
