from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.relations import RelationsBatch
from szurubooru_toolkit.szurubooru import SzurubooruError


@logger.catch
def main(query: str) -> None:
    """
    Complete post relation sets by computing their transitive closure.

    Posts uploaded one by one only reference the posts that existed at their upload
    time: in a set of three, post 2 references post 1 but never learns about post 3.
    This script collects the existing relations of all posts matching the query,
    groups them into sets via transitive closure, and writes the complete member
    list to every member. Posts related to matching posts are included in their
    sets even if they don't match the query themselves.

    Args:
        query (str): The query to use for retrieving posts.

    Returns:
        None
    """

    try:
        try:
            hide_progress = config.globals['hide_progress']
        except KeyError:
            hide_progress = config.fix_relations['hide_progress']

        posts = szuru.get_posts(query, videos=True)

        try:
            total_posts = next(posts)
        except StopIteration:
            logger.info(f'Found no posts for your query: {query}')
            exit()

        logger.info(f'Found {total_posts} posts. Collecting relation sets...')

        batch = RelationsBatch()

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
            if post.relations:
                batch.add(post.id, [relation['id'] for relation in post.relations])

        updated = batch.reconcile(szuru)

        if not updated:
            logger.info('All relation sets were already complete.')

        logger.success('Finished fixing relations!')
    except SzurubooruError as e:
        logger.critical(f'Could not process your query: {e}')
        exit(1)
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
