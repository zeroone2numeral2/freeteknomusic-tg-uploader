import math
from pathlib import Path

import eyed3

import utilities as utilities
from config import config

logger = utilities.get_logger(__file__)


DAY_SECONDS = 86400
HOUR_SECONDS = 3600
MINUTE_SECONDS = 60


def main():
    allowed_extensions = tuple(config.tracks.allowed_extensions)
    logger.info(f"allowed extensions: {allowed_extensions}")

    tracks_path = Path(config.tracks.path)
    total_duration = 0
    tracks_count_with_duration = 0
    tracks_count_without_duration = 0
    for file_path in tracks_path.rglob("*"):
        if file_path.is_dir():
            continue

        if not file_path.name.lower().endswith(allowed_extensions):
            logger.opt(colors=True).info(f"<y>not an mp3</y>: {file_path.parent} -> {file_path.name}")
            continue

        try:
            audio_file = eyed3.load(file_path)
        except UnicodeDecodeError:
            logger.warning(f"UnicodeDecodeError: {file_path}")
            tracks_count_without_duration += 1
            continue

        if not audio_file:
            logger.warning(f"couldn't load file: {file_path}")
            tracks_count_without_duration += 1
            continue
        elif not audio_file.info or not audio_file.info.time_secs:
            logger.warning(f"couldn't read file duration: {file_path}")
            tracks_count_without_duration += 1
            continue

        total_duration += audio_file.info.time_secs
        tracks_count_with_duration += 1

    # calculate the average duration and sum it to the total for every track that doesn't have a duration
    average_duration = total_duration / tracks_count_with_duration
    total_duration += average_duration * tracks_count_without_duration

    logger.info(f"{tracks_count_with_duration} tracks + {tracks_count_without_duration} without duration, tot {total_duration} seconds")

    days = total_duration // DAY_SECONDS
    total_duration = total_duration % DAY_SECONDS

    hours = total_duration // HOUR_SECONDS
    total_duration %= HOUR_SECONDS

    minutes = total_duration // MINUTE_SECONDS
    total_duration %= MINUTE_SECONDS

    seconds = int(total_duration)

    logger.info(f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds")


if __name__ == '__main__':
    main()
