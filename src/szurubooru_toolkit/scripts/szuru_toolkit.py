import importlib
import shutil
import types

import click
from click.core import ParameterSource

from szurubooru_toolkit import config
from szurubooru_toolkit import setup_clients
from szurubooru_toolkit import setup_config
from szurubooru_toolkit import setup_logger


def setup_module(module_name: str, click_context: click.core.Context) -> types.ModuleType:
    """Sets up and validates the configuration, clients, and logger, then imports and returns the specified module.

    This function first calls `setup_config` and `setup_logger` to set up the configuration and logger.
    It then overrides the configuration with the options passed to the Click command, and validates the configuration.
    After that, it sets up the clients and imports the specified module from the `szurubooru_toolkit.scripts` package.
    If the module name is 'import-from-url' or 'upload_media', it also validates the path in the configuration.

    Args:
        module_name (str): The name of the module to import from the `szurubooru_toolkit.scripts` package.
        click_context (click.core.Context): The Click context object, which contains the options passed to the Click command.

    Returns:
        The imported module.
    """

    setup_config()
    setup_logger()

    from szurubooru_toolkit import config

    config.override_config(click_context.obj)

    setup_clients()
    module = importlib.import_module('szurubooru_toolkit.scripts.' + module_name)

    if module_name in ['import_from_url', 'upload_media']:
        config.validate_path()

    return module


CONTEXT_SETTINGS = {'help_option_names': ['-h', '--help'], 'max_content_width': shutil.get_terminal_size().columns - 10}


@click.group(context_settings=CONTEXT_SETTINGS)
# Global Options
@click.option('--url', help='Base URL to your szurubooru instance.')
@click.option('--username', help='Username which will be used to authenticate with the szurubooru API.')
@click.option('--api-token', help='API token for the user which will be used to authenticate with the szurubooru API.')
@click.option(
    '--public',
    is_flag=True,
    help=f'If your szurubooru instance is reachable from the internet (default: {config.GLOBALS_DEFAULTS["public"]}).',
)
# Logging options
@click.option('--log-enabled', is_flag=True, help=f'Create a log file (default: {config.LOGGING_DEFAULTS["log_enabled"]}).')
@click.option('--log-colorized', is_flag=True, help=f'Colorize the log output (default: {config.LOGGING_DEFAULTS["log_colorized"]}).')
@click.option('--log-file', help=f'Output file for the log (default: {config.LOGGING_DEFAULTS["log_file"]})')
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=True),
    help=f'Set the log level (default: {config.LOGGING_DEFAULTS["log_level"]}).',
)
@click.option(
    '--hide-progress',
    is_flag=True,
    help='Hides the progress bar (default: False).',
)  # Don't use config.GLOBALS_DEFAULTS here, because we use that option with a try/except block
@click.pass_context
def cli(
    ctx,
    url,
    username,
    api_token,
    public,
    log_enabled,
    log_colorized,
    log_file,
    log_level,
    hide_progress,
):
    """Toolkit to manage your szurubooru image board.

    Defaults can also be set in a config file.

    Visit https://github.com/reluce/szurubooru-toolkit for more information.
    """

    user_params = {}
    ctx.ensure_object(dict)

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            user_params[param.name] = ctx.params[param.name]

    for item, value in user_params.items():
        if item in ['url', 'username', 'api_token', 'public']:
            ctx.obj.setdefault('globals', {}).update({item: value})
        elif item in ['log', 'log_colorized', 'log_file', 'log_level']:
            ctx.obj.setdefault('logging', {}).update({item: value})
        elif item in [
            'hide_progress',
            'convert_to_jpg',
            'convert_threshold',
            'default_safety',
            'max_similarity',
            'shrink',
            'shrink_threshold',
            'shrink_dimensions',
        ]:
            ctx.obj.setdefault('globals', {}).update({item: value})


@cli.command('auto-tagger', epilog='Example: szuru-toolkit auto-tagger --add-tags "foo,bar" --no-saucenao "tag-count:..2 date:today"')
@click.argument('query')
@click.option('--add-tags', help='Specify tags, separated by a comma, which will be added to all posts matching your query.')
@click.option('--remove-tags', help='Specify tags, separated by a comma, which will be removed from all posts matching your query.')
@click.option('--saucenao/--no-saucenao', help=f'Search for posts with SauceNAO (default: {config.AUTO_TAGGER_DEFAULTS["saucenao"]}).')
@click.option('--saucenao-api-token', help='Your SauceNAO API token. Increases daily limits.')
@click.option(
    '--md5-search/--no-md5-search',
    help=f'Search for posts with the same MD5 hash on popular boorus (default: {config.AUTO_TAGGER_DEFAULTS["md5_search"]}).',
)
@click.option(
    '--limit',
    help=f'Set the limit for the number of tagged elements (default: {config.AUTO_TAGGER_DEFAULTS["limit"]}).',
)
@click.option(
    '--deepbooru/--no-deepbooru',
    is_flag=True,
    help=f'Tag posts with Deepbooru if file could not be found (default: {config.AUTO_TAGGER_DEFAULTS["deepbooru"]}).',
)
@click.option('--deepbooru-model', help='Path to the Deepbooru model.')
@click.option(
    '--deepbooru-threshold',
    help=f'Define how accurate the matched tag from Deepbooru has to be (default: {config.AUTO_TAGGER_DEFAULTS["deepbooru_threshold"]}).',
)
@click.option(
    '--deepbooru-forced/--no-deepbooru-forced',
    help=(
        'Always tag with SauceNAO and Deepbooru. Overwrites deepbooru-enabled (default:'
        f' {config.AUTO_TAGGER_DEFAULTS["deepbooru_forced"]}).'
    ),
)
@click.option(
    '--deepbooru-set-tag/--no-deepbooru-set-tag',
    is_flag=True,
    help=f'Tag Deepbooru posts with tag "deepbooru" (default: {config.AUTO_TAGGER_DEFAULTS["deepbooru_set_tag"]}).',
)
@click.option(
    '--update-relations/--dont-update-relations',
    help=(
        'Set character <> parody relation if SauceNAO is disabled (or limit reached) and Deepbooru enabled (default:'
        f' {config.AUTO_TAGGER_DEFAULTS["update_relations"]}).'
    ),
)
@click.option(
    '--use-pixiv-artist/--dont-use-pixiv-artist',
    is_flag=True,
    help=(
        'If the artist could only be found on pixiv, create and use the pixiv artist (default:'
        f' {config.AUTO_TAGGER_DEFAULTS["use_pixiv_artist"]}).'
    ),
)
@click.option(
    '--use-pixiv-tags/--dont-use-pixiv-tags',
    is_flag=True,
    help=(
        'If the post could only be found on pixiv, create and use the pixiv tags (default:'
        f' {config.AUTO_TAGGER_DEFAULTS["use_pixiv_tags"]}).'
    ),
)
@click.pass_context
def click_auto_tagger(
    ctx,
    query,
    add_tags,
    remove_tags,
    saucenao,
    saucenao_api_token,
    md5_search,
    limit,
    deepbooru,
    deepbooru_model,
    deepbooru_threshold,
    deepbooru_forced,
    deepbooru_set_tag,
    update_relations,
    use_pixiv_artist,
    use_pixiv_tags,
):
    """
    Tag posts automatically

    Tags can be searched through SauceNAO, the MD5 hash on popular boorus or Deepbooru.

    QUERY is a szurubooru query for posts to tag.
    """

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('auto_tagger', {}).update({param.name: ctx.params[param.name]})

    module = setup_module('auto_tagger', ctx)

    from loguru import logger

    if add_tags:
        logger.debug(f'add_tags = {add_tags}')
        add_tags = add_tags.replace(' ', '').split(',')
    if remove_tags:
        remove_tags = remove_tags.replace(' ', '').split(',')
        logger.debug(f'remove_tags = {remove_tags}')

    module.main(query, add_tags, remove_tags)


@cli.command('create-relations', epilog='Example: szuru-toolkit create-relations hitori_bocchi')
@click.argument('query')
@click.option(
    '--threshold',
    type=int,
    help=(
        'How many posts should exist at minimum with character + parody to create their relation (default:'
        f' {config.CREATE_RELATIONS_DEFAULTS["threshold"]}).'
    ),
)
@click.pass_context
def click_create_relations(ctx, query, threshold):
    """
    Create relations between character and parody tag categories

    QUERY is a szurubooru query you want to create relations for.
    """

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj['create_relations'] = {param.name: ctx.params[param.name]}

    module = setup_module('create_relations', ctx)
    module.main(query)


@cli.command('create-tags', epilog='Example: szuru-toolkit create-tags --query "genshin*" --overwrite')
@click.option(
    '--tag-file',
    help='Specify a file containing tags and categories. If specified, ignores other arguments.',
)
@click.option('--query', help=f'Search for specific tags (default: {config.CREATE_TAGS_DEFAULTS["query"]}).')
@click.option(
    '--limit',
    type=int,
    help=(
        f'The amount of tags that should be downloaded. Start from the most recent ones (default: {config.CREATE_TAGS_DEFAULTS["limit"]}).'
    ),
)
@click.option(
    '--min-post-count',
    type=int,
    help=f'The minimum amount of posts the tag should have been used in (default: {config.CREATE_TAGS_DEFAULTS["min_post_count"]}).',
)
@click.option(
    '--overwrite/--no-overwrite',
    help=f'Overwrite tag category if the tag already exists (default: {config.CREATE_TAGS_DEFAULTS["overwrite"]}).',
)
@click.pass_context
def click_create_tags(ctx, tag_file, query, limit, min_post_count, overwrite):
    """
    Create tags based on a tag file or query
    """

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('create_tags', {}).update({param.name: ctx.params[param.name]})

    module = setup_module('create_tags', ctx)
    module.main(tag_file)


@cli.command('delete-posts', epilog='Example: szuru-toolkit delete-posts --except-ids "12,23,44" "id:10..50"')
@click.argument('query')
@click.option('--except-ids', help='Specify the post ids, separated by a comma, which should not be deleted.')
@click.pass_context
def click_delete_posts(ctx, query, except_ids):
    """
    Delete posts

    QUERY is a szurubooru query for posts to delete.
    """

    module = setup_module('delete_posts', ctx)

    from loguru import logger

    if except_ids:
        except_ids = except_ids.replace(' ', '').split(',')
        logger.debug(f'except_ids = {except_ids}')
    else:
        except_ids = []

    module.main(query, except_ids)


@cli.command('import-from-booru', epilog='Example: szuru-toolkit import-from-booru --booru danbooru "tag1 tagN"')
@click.argument('query')
@click.option(
    '--booru',
    type=click.Choice(['danbooru', 'gelbooru', 'konachan', 'sankaku', 'yandere', 'all'], case_sensitive=False),
    required=True,
    help='Specify the booru you want to download posts from.',
)
@click.option(
    '--limit',
    type=int,
    help=f'The amount of posts that should be imported (default: {config.IMPORT_FROM_BOORU_DEFAULTS["limit"]}).',
)
@click.option(
    '--deepbooru/--no-deepbooru',
    help=f'Tag posts additionally with Deepbooru (default: {config.IMPORT_FROM_BOORU_DEFAULTS["deepbooru"]}).',
)
@click.option(
    '--convert-to-jpg/--no-convert-to-jpg',
    help=f'Convert images to JPG if convert-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["convert_to_jpg"]}).',
)
@click.option(
    '--convert-threshold',
    help=(
        'Convert images to JPG if the file size is bigger than this threshold (default:'
        f' {config.UPLOAD_MEDIA_DEFAULTS["convert_threshold"]}).'
    ),
)
@click.option(
    '--default-safety',
    type=click.Choice(['safe', 'sketchy', 'unsafe'], case_sensitive=True),
    help=f'Default safety level for posts if it couldn\'t be detectecd (default: {config.UPLOAD_MEDIA_DEFAULTS["default_safety"]}).',
)
@click.option(
    '--max-similarity',
    type=int,
    help=f'Images that exceeds this value won\'t get uploaded (default: {config.UPLOAD_MEDIA_DEFAULTS["max_similarity"]}).',
)
@click.option(
    '--shrink/--no-shrink',
    help=f'Shrink images if shrink-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink"]}).',
)
@click.option(
    '--shrink-threshold',
    type=int,
    help=f'Images which total pixel count exceeds this value will be shrunk (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_threshold"]}).',
)
@click.option(
    '--shrink-dimensions',
    help=f'Maximum width and height of the shrunken image (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_dimensions"]}).',
)
@click.option('--limit', type=int, help=f'Limit the search results to be returned (default: {config.IMPORT_FROM_BOORU_DEFAULTS["limit"]}).')
@click.pass_context
def click_import_from_booru(
    ctx,
    query,
    booru,
    limit,
    deepbooru,
    convert_to_jpg,
    convert_threshold,
    default_safety,
    max_similarity,
    shrink,
    shrink_threshold,
    shrink_dimensions,
):
    """
    Download and tag posts from various Boorus

    QUERY is a query you want to search for.
    """

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('import_from_booru', {}).update({param.name: ctx.params[param.name]})

    module = setup_module('import_from_booru', ctx)
    module.main(booru, query)


@cli.command(
    'import-from-url',
    epilog='Example: szuru-toolkit import-from-url --cookies "~/cookies.txt" --range ":100" "https://twitter.com/<USERNAME>/likes"',
)
@click.argument('urls', nargs=-1)
@click.option('--input-file', help='Download URLs found in FILE')
@click.option(
    '--range',
    help=(
        'Index range(s) specifying which files to download. These can be either a constant value, range, or slice (default:'
        f' {config.IMPORT_FROM_URL_DEFAULTS["range"]}).'
    ),
)
@click.option('--cookies', help='Path to a cookies file for gallery-dl to consume. Used for authentication.')
@click.option(
    '--deepbooru/--no-deepbooru',
    help=f'Tag posts additionally with Deepbooru (default: {config.IMPORT_FROM_URL_DEFAULTS["deepbooru"]}).',
)
@click.option(
    '--md5-search/--no-md5-search',
    help=f'Search for posts with the same MD5 hash on popular boorus (default: {config.IMPORT_FROM_URL_DEFAULTS["md5_search"]}).',
)
@click.option('--saucenao/--no-saucenao', help=f'Search for posts with SauceNAO (default: {config.IMPORT_FROM_URL_DEFAULTS["saucenao"]}).')
@click.option(
    '--use-twitter-artist/--dont-use-twitter-artist',
    help=f'Create Twitter username and nickname tags for the artist (default: {config.IMPORT_FROM_URL_DEFAULTS["use_twitter_artist"]}).',
)
@click.option(
    '--convert-to-jpg/--no-convert-to-jpg',
    help=f'Convert images to JPG if convert-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["convert_to_jpg"]}).',
)
@click.option(
    '--convert-threshold',
    help=(
        'Convert images to JPG if the file size is bigger than this threshold (default:'
        f' {config.UPLOAD_MEDIA_DEFAULTS["convert_threshold"]}).'
    ),
)
@click.option(
    '--default-safety',
    type=click.Choice(['safe', 'sketchy', 'unsafe'], case_sensitive=True),
    help=f'Default safety level for posts if it couldn\'t be detectecd (default: {config.UPLOAD_MEDIA_DEFAULTS["default_safety"]}).',
)
@click.option(
    '--max-similarity',
    type=int,
    help=f'Images that exceeds this value won\'t get uploaded (default: {config.UPLOAD_MEDIA_DEFAULTS["max_similarity"]}).',
)
@click.option(
    '--shrink/--no-shrink',
    help=f'Shrink images if shrink-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink"]}).',
)
@click.option(
    '--shrink-threshold',
    type=int,
    help=f'Images which total pixel count exceeds this value will be shrunk (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_threshold"]}).',
)
@click.option(
    '--shrink-dimensions',
    help=f'Maximum width and height of the shrunken image (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_dimensions"]}).',
)
@click.option('--add-tags', help='Specify tags, separated by a comma, which will be added to all posts.')
@click.option(
    '--update-tags-if-exists/--dont-update-tags-if-exists',
    is_flag=True,
    help=f'Append new tags, if any, to already uploaded posts (default: {config.IMPORT_FROM_URL_DEFAULTS["update_tags_if_exists"]}).',
)
@click.option('--verbose', is_flag=True, help='Show download progress of gallery-dl script.')
@click.pass_context
def click_import_from_url(
    ctx,
    urls,
    input_file,
    range,
    cookies,
    deepbooru,
    md5_search,
    saucenao,
    use_twitter_artist,
    convert_to_jpg,
    convert_threshold,
    default_safety,
    max_similarity,
    shrink,
    shrink_threshold,
    shrink_dimensions,
    add_tags,
    update_tags_if_exists,
    verbose,
):
    """
    Download images from URLS or file containing URLs

    URLS is a comma-separated list of URLs to download images from.
    """

    if not urls and not input_file:
        click.echo(ctx.get_help())
        click.echo('\nYou need to specify either URLs or --input-file!')
        exit(1)

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('import_from_url', {}).update({param.name: ctx.params[param.name]})

    module = setup_module('import_from_url', ctx)

    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
        from loguru import logger

        logger.debug(f'add_tags = {add_tags}')
    else:
        add_tags = []

    module.main(list(urls), input_file, add_tags, verbose)


@cli.command('reset-posts', epilog='Example: szuru-toolkit reset-posts reset-posts --except-ids "2,4" --add-tags "tagme,foo" "foobar"')
@click.argument('query')
@click.option('--except-ids', help='Specify the post ids, separated by a comma, which should not be reset.')
@click.option(
    '--add-tags',
    help='Specify tags, separated by a comma, which will be added to all posts matching your query after resetting.',
)
@click.pass_context
def click_reset_posts(ctx, query, except_ids, add_tags):
    """
    Remove tags and sources

    QUERY is a szurubooru query for posts to reset.
    """

    module = setup_module('reset_posts', ctx)

    from loguru import logger

    if except_ids:
        except_ids = except_ids.replace(' ', '').split(',')
        logger.debug(f'except_ids = {except_ids}')
    else:
        except_ids = []

    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
        logger.debug(f'add_tags = {add_tags}')
    else:
        add_tags = []

    module.main(query, except_ids, add_tags)


@cli.command('tag-posts', epilog='Example: szuru-toolkit tag-posts --add-tags "foo,bar" --remove-tags "baz" "foo"')
@click.argument('query')
@click.option('--add-tags', help='Specify tags, separated by a comma, which will be added to all posts matching your query.')
@click.option('--remove-tags', help='Specify tags, separated by a comma, which will be removed from all posts matching your query.')
@click.option('--source', help='Set the source of the post')
@click.option(
    '--mode',
    type=click.Choice(['overwrite', 'append'], case_sensitive=False),
    help=f'Set mode to overwrite to remove already set tags, set append to keep them (default: {config.TAG_POSTS_DEFAULTS["mode"]}).',
)
@click.option(
    '--update-implications/--dont-update-implications',
    help=(
        'Fetches all tags from the posts matching the query and updates them if tag implications are missing (default:'
        f' {config.TAG_POSTS_DEFAULTS["update_implications"]}).'
    ),
)
@click.pass_context
def click_tag_posts(ctx, query, add_tags, remove_tags, source, mode, update_implications):
    """
    Tag posts manually

    QUERY is a szurubooru query for posts to tag.
    """

    if not add_tags and not remove_tags and not source and not update_implications:
        print(ctx.get_help())
        click.echo('\nYou need to specify either --add-tags, --remove-tags, --source or --update-implications as an argument!')
        exit(1)

    module = setup_module('tag_posts', ctx)

    from loguru import logger

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('tag_posts', {}).update({param.name: ctx.params[param.name]})

    if add_tags:
        add_tags = add_tags.replace(' ', '').split(',')
        logger.debug(f'add_tags = {add_tags}')
    if remove_tags:
        remove_tags = remove_tags.replace(' ', '').split(',')
        logger.debug(f'remove_tags = {remove_tags}')

    module.main(query, add_tags, remove_tags, source)


@cli.command('upload-media', epilog='Example: szuru-toolkit upload-media --auto-tag --cleanup --tags "foo,bar"')
@click.argument('src-path', required=False)
@click.option('--auto-tag/--no-auto-tag', help=f'Tag posts automatically (default: {config.UPLOAD_MEDIA_DEFAULTS["auto_tag"]}).')
@click.option(
    '--cleanup/--no-cleanup',
    help=f'Remove the source files after uploading it (default: {config.UPLOAD_MEDIA_DEFAULTS["cleanup"]}).',
)
@click.option(
    '--tags',
    help=f'Specify tags, separated by a comma, which will be added to all posts (default: {config.UPLOAD_MEDIA_DEFAULTS["tags"]}).',
)
@click.option(
    '--convert-to-jpg/--no-convert-to-jpg',
    help=f'Convert images to JPG if convert-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["convert_to_jpg"]}).',
)
@click.option(
    '--convert-threshold',
    help=(
        'Convert images to JPG if the file size is bigger than this threshold (default:'
        f' {config.UPLOAD_MEDIA_DEFAULTS["convert_threshold"]}).'
    ),
)
@click.option(
    '--default-safety',
    type=click.Choice(['safe', 'sketchy', 'unsafe'], case_sensitive=True),
    help=f'Default safety level for posts if it couldn\'t be detectecd (default: {config.UPLOAD_MEDIA_DEFAULTS["default_safety"]}).',
)
@click.option(
    '--max-similarity',
    type=int,
    help=f'Images that exceeds this value won\'t get uploaded (default: {config.UPLOAD_MEDIA_DEFAULTS["max_similarity"]}).',
)
@click.option(
    '--shrink/--no-shrink',
    help=f'Shrink images if shrink-threshold is exceeded (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink"]}).',
)
@click.option(
    '--shrink-threshold',
    type=int,
    help=f'Images which total pixel count exceeds this value will be shrunk (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_threshold"]}).',
)
@click.option(
    '--shrink-dimensions',
    help=f'Maximum width and height of the shrunken image (default: {config.UPLOAD_MEDIA_DEFAULTS["shrink_dimensions"]}).',
)
@click.pass_context
def click_upload_media(
    ctx,
    src_path,
    cleanup,
    tags,
    auto_tag,
    convert_to_jpg,
    convert_threshold,
    default_safety,
    max_similarity,
    shrink,
    shrink_threshold,
    shrink_dimensions,
):
    """
    Upload media files

    SRC_PATH is the path to the media files you want to upload.
    """

    for param in ctx.command.params:
        parameter_source = click.get_current_context().get_parameter_source(param.name)
        if parameter_source == ParameterSource.COMMANDLINE:
            ctx.obj.setdefault('upload_media', {}).update({param.name: ctx.params[param.name]})

    module = setup_module('upload_media', ctx)
    module.main()


if __name__ == '__main__':
    cli()
