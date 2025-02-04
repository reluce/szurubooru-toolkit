from loguru import logger
from tqdm import tqdm

from szurubooru_toolkit import config
from szurubooru_toolkit import szuru
from szurubooru_toolkit.utils import collect_sources


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

        for post in tqdm(
            posts,
            ncols=80,
            position=0,
            leave=False,
            total=int(total_posts),
            disable=hide_progress,
        ):
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
                    szuru_tag = szuru.api.getTag(tag)
                    for implication in szuru_tag.implications:
                        szuru_implication = szuru.api.getTag(implication)
                        if szuru_implication not in post.tags:
                            post.tags.append(szuru_implication.primary_name)

            szuru.update_post(post)

        if not config.tag_posts['silence_info']:
            logger.success('Finished tagging!')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt from user.')
        exit(1)


if __name__ == '__main__':
    main()
