import glob
from pathlib import Path

from loguru import logger
import psycopg2
from tqdm import tqdm

from szurubooru_toolkit import config


@logger.catch
def main() -> None:
    """
    Main function to handle updating the database creation times for the imported files.
    Returns:
        None
    """
    cfg = config.update_db_timestamps

    if ('imported_post_timestamps_dir' not in cfg
        or cfg['imported_post_timestamps_dir'] is None
        or not Path(cfg['imported_post_timestamps_dir']).exists()):
        logger.error('Failed to import because the post timestamp directory is not set.')
        return
    files = [file for file in glob.glob(f"{cfg['imported_post_timestamps_dir']}/*") if Path(file).suffix in ['.timestamp']]
    logger.info(f'Found {len(files)} file(s). Start updating database...')
    if len(files) == 0:
        logger.info("Nothing to process")
        return

    try:
        conn = psycopg2.connect(f"host={cfg['db_host']} port={cfg['db_port']} dbname={cfg['db_name']} user={cfg['db_user']} password={cfg['db_password']}")
        cur = conn.cursor()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f"Failed to open connection with database, please check your credentials.")
        logger.error(error)
        exit(1)

    try:
        hide_progress = config.globals['hide_progress']
    except KeyError:
        hide_progress = cfg['hide_progress']

    files_success = []
    for file in tqdm(
        files,
        ncols=80,
        position=0,
        leave=False,
        disable=hide_progress,
    ):
        with open(file, 'r') as f:
            timestamp = f.read().strip()
            if not timestamp or len(timestamp) == 0:
                tqdm.write(f"Timestamp is empty for {file}")
                continue

            postid = Path(file).stem
            try:
                cur.execute(f"UPDATE post SET creation_time = '{timestamp}' WHERE id = '{postid}'")
                if cur.rowcount == 1:
                    files_success.append(file)
                else:
                    tqdm.write(f"Could not update post id {postid}.")
            except:
                tqdm.write(f"Failed to update timestamp to {timestamp} for post id {postid}.")

    if len(files_success) > 0:
        # Write the changes to the database.
        try:
            conn.commit()
            conn.close()
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f"Failed to commit the changes.")
            logger.error(error)
            exit(2)

        # Delete the processed files.
        if cfg['delete_files']:
            for file in files_success:
                Path(file).unlink()

    logger.success(f'Finished updating the date times for {len(files_success)} out of {len(files)} files!')


if __name__ == '__main__':
    main()
