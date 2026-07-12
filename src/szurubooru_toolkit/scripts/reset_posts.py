from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import run_concurrently


@logger.catch
def main(query: str, except_ids: list = [], add_tags: list = []) -> None:
    """
    Retrieve the posts from input query and reset them in szurubooru.

    Args:
        query (str): The query to use for retrieving posts.
        except_ids (list, optional): A list of post IDs that should not be reset. Defaults to [].
        add_tags (list, optional): A list of tags to add to the reset posts. Defaults to [].

    Returns:
        None
    """

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.reset_posts['hide_progress']

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Start resetting...')
        if except_ids:
            logger.info(f'Won\'t reset the following ids: {except_ids}')

        def worker(post) -> None:
            if post.id not in except_ids:
                post.tags = add_tags if add_tags else []
                post.source = ''
                szuru.update_post(post)

        workers = max(1, int(config.reset_posts['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), hide_progress)

        logger.success('Finished resetting!')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
