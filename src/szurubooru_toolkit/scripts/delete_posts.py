from loguru import logger

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.szurubooru import SzurubooruError
from szurubooru_toolkit.utils import run_concurrently


@logger.catch
def main(query: str, except_ids: str) -> None:
    """
    Retrieve the posts from input query and delete them in szurubooru.

    Args:
        query (str): The query to use for retrieving posts.
        except_ids (str): A comma-separated string of post IDs that should not be deleted.

    Returns:
        None
    """

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.delete_posts['hide_progress']

        logger.debug(f'query = {query}')

        if except_ids:
            except_ids = except_ids.replace(' ', '').split(',')
            logger.debug(f'except_ids = {except_ids}')

        posts = szuru.get_posts(query, pagination=False, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Start deleting...')
        if except_ids:
            logger.info(f'Won\'t delete the following ids: {except_ids}')

        def worker(post) -> None:
            if post.id not in except_ids:
                szuru.delete_post(post)

        workers = max(1, int(config.delete_posts['workers']))
        run_concurrently(posts, worker, workers, int(total_posts), hide_progress)

        logger.success('Finished deleting!')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
