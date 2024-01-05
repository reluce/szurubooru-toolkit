from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru


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

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
            if post.id not in except_ids:
                szuru.delete_post(post)

        logger.success('Finished deleting!')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
