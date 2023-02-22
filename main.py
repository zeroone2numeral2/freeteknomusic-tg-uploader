import io
import os
from pathlib import Path
import asyncio
import datetime
from typing import Optional, Union, List
from typing import TypedDict

import eyed3
from eyed3.id3.frames import ImageFrame
from eyed3.mp3 import Mp3AudioFile
from pyrogram import Client
from pyrogram.errors import FloodWait
from tqdm import tqdm

import utilities as utilities
from config import config

logger = utilities.get_logger(__file__)


class Id2Kwargs(TypedDict):
    title: Optional[str]
    performer: Optional[str]
    thumb: Optional[io.BytesIO]
    duration: Optional[int]
    caption: Optional[str]


class FileName:
    PROCESSED_TRACKS = "data/processed-tracks.json"
    POSTED_MESSAGES = "data/posted-messages.json"


FILE_SIZE_LIMIT_MIB = 2000


app = Client(**config.pyrogram, **config.bot_account, workers=1, no_updates=True)
app.start()

processed = utilities.StorageList(FileName.PROCESSED_TRACKS, init_object=[], autosave=True)
posted_messages = utilities.StoragMessages(FileName.POSTED_MESSAGES, autosave=True)

DEFAULT_THUMBNAIL: Optional[io.BytesIO] = None
if config.tracks.default_thumbnail_path:
    try:
        with open(config.tracks.default_thumbnail_path, "rb") as f:
            DEFAULT_THUMBNAIL = io.BytesIO(f.read())
    except FileNotFoundError:
        logger.warning(f"unable to find default thumbnail file: {config.tracks.default_thumbnail_path}")


class ProgressBar:
    def __init__(self):
        self.last_update_perc = 0
        self.tqdm = None


async def progress(current, total, progress_bar: ProgressBar):
    if not progress_bar.tqdm:
        progress_bar.tqdm = tqdm(total=100, leave=False, bar_format="[{bar}]{percentage:3.0f}% (elapsed: {elapsed})")

    proggress_perc = current * 100 / total
    progress_step = proggress_perc - progress_bar.last_update_perc
    progress_bar.last_update_perc = proggress_perc

    progress_bar.tqdm.update(progress_step)

    logger.debug(f"{proggress_perc:.1f}%")


def override_artwork(audio_file):
    # if p.name.startswith("B"):

    audio_file.tag.images.set(
        ImageFrame.FRONT_COVER,
        open('thumb.jpg', 'rb').read(),
        "image/jpeg", u"artwork"
    )
    audio_file.tag.save()


def extract_date(audio_file: Mp3AudioFile):
    # date fields are actually datetime objects, we don't care about the time so we only return the date
    if audio_file.tag.original_release_date:
        tag_date = audio_file.tag.original_release_date
    elif audio_file.tag.release_date:
        tag_date = audio_file.tag.release_date
    elif audio_file.tag.recording_date:
        tag_date = audio_file.tag.recording_date
    else:
        return

    if tag_date.year:
        return tag_date.year


def artist_from_path(file_path: Path, join: str, remove_first_n_directories: int = 0) -> Optional[str]:
    parts_list_no_filename = list(file_path.parts)[:-1]

    # remove the first file path directories
    parts_list_no_leading_dirs = parts_list_no_filename[remove_first_n_directories:]

    if not parts_list_no_leading_dirs:
        return

    return join.join(parts_list_no_leading_dirs)


async def process_audio_file(file_path: Path, current_file_index: int, files_count: int):
    logger.info(f"{file_path.parent} -> {file_path.name}")

    # load() might return None if the mime type is not recognized
    # http://eyed3.readthedocs.io/en/latest/eyed3.html#eyed3.core.load
    try:
        audio_file: Optional[Mp3AudioFile] = eyed3.load(file_path)
    except UnicodeDecodeError:
        # must investigate
        logger.warning(f"UnicodeDecodeError while decoding metadata for file {file_path}")
        audio_file = None

    if audio_file and audio_file.info and audio_file.info.size_bytes:
        size_str = utilities.human_readable_size(audio_file.info.size_bytes)
        logger.info(f"\tsize:     {size_str}")
        if audio_file.info.size_bytes > FILE_SIZE_LIMIT_MIB * 1024 * 1024:
            logger.warning(f"file is too big")
            logger.warning(f"send it manually and add it to {FileName.PROCESSED_TRACKS} and {FileName.POSTED_MESSAGES}")
            return False

    if DEFAULT_THUMBNAIL:
        DEFAULT_THUMBNAIL.seek(0)

    id3_kwargs: Id2Kwargs = dict(
        title=file_path.stem,  # stem = no extension
        performer=artist_from_path(file_path, " - ", config.tracks.remove_first_n_directories_from_path_artist),
        thumb=DEFAULT_THUMBNAIL,
        caption=None,
        duration=int(audio_file.info.time_secs) if audio_file and audio_file.info and audio_file.info.time_secs else 0
    )

    logger.opt(colors=True).info(f"\tduration: {datetime.timedelta(seconds=id3_kwargs['duration']) or '<r>not found</r>'}")

    if not audio_file or not audio_file.tag:
        logger.info(f"\ttitle:    {id3_kwargs['title']}")
        logger.info(f"\tartist:   {id3_kwargs['performer']}")
        logger.opt(colors=True).info(f"\t<r>couldn't load id3 metadata</r>")
    else:
        # do not clorize these tags: https://github.com/Delgan/loguru/issues/140

        if audio_file.tag.title:
            logger.info(f"\ttitle:    [ID3] {audio_file.tag.title}")
            id3_kwargs["title"] = audio_file.tag.title
        else:
            logger.info(f"\ttitle:    {id3_kwargs['title']}")

        if audio_file.tag.artist:
            logger.info(f"\tartist:   [ID3] {audio_file.tag.artist}")
            id3_kwargs["performer"] = audio_file.tag.artist
        else:
            logger.info(f"\tartist:   {id3_kwargs['performer']}")

        logger.info(f"\talbum:    {audio_file.tag.album or '-'}")
        if audio_file.tag.album:
            id3_kwargs["caption"] = f"💽 {audio_file.tag.album}"
            album_year = extract_date(audio_file)
            if album_year:
                id3_kwargs["caption"] += f" ({album_year})"

        if not audio_file.tag.images:
            logger.info(f"\tartwork:  -")
        else:
            thumb = io.BytesIO(audio_file.tag.images[0].image_data)

            thumb.seek(0, os.SEEK_END)
            file_size = thumb.tell()
            thumb.seek(0)

            if file_size != 0:
                id3_kwargs["thumb"] = thumb
                logger.info(f"\tartwork:  found")
            else:
                logger.opt(colors=True).info(f"\tartwork:  <r>thumbnail found, but size is 0</r>")

    retry = True
    while retry:
        try:
            logger.opt(colors=True).info("<g>uploading...</g>")
            progress_bar = ProgressBar()
            message = await app.send_audio(
                config.telegram.chat_id,
                file_path,
                file_name=file_path.name,
                disable_notification=True,
                progress=progress,
                progress_args=(progress_bar,),
                **id3_kwargs
            )
            logger.opt(colors=True).info(f"<g>...upload completed</g>, {files_count - current_file_index} pending")
            processed.add(file_path)
            posted_messages.add(message.id, file_path)
            retry = False
            progress_bar.tqdm.close()
        except FloodWait as e:
            logger.opt(colors=True).info(f"<r>flood_wait: will retry in {e.value} seconds</r>")
            await asyncio.sleep(e.value + 180)


async def send_dir_name(file_path: Path, pin=True):
    text = artist_from_path(file_path, " -> ", config.tracks.remove_first_n_directories_from_path)
    message = await app.send_message(config.telegram.chat_id, text, disable_web_page_preview=True)
    posted_messages.add(message.id, message.text)

    if not pin:
        return

    retry = True
    while retry:
        try:
            logger.info(f"pinning message {message.id} (and then sleeping {config.tracks.message_pinning_cooldown} seconds)...")
            service_message = await message.pin(disable_notification=True)
            retry = False
            await service_message.delete()

            # always sleep after pinning
            await asyncio.sleep(config.tracks.message_pinning_cooldown)
        except FloodWait as e:
            logger.opt(colors=True).info(f"<r>flood_wait while pinning: will retry in {e.value} seconds</r>")
            await asyncio.sleep(e.value + 5)


async def main():
    tracks_path = Path(config.tracks.path)
    last_dir_name = ""
    allowed_extensions = tuple(config.tracks.allowed_extensions)
    logger.info(f"allowed extensions: {allowed_extensions}")

    paths_list: List[Path] = []

    for file_path in tracks_path.rglob("*"):
        if file_path.is_dir():
            continue

        if not file_path.name.lower().endswith(allowed_extensions):
            logger.opt(colors=True).info(f"<y>{file_path.suffix} file ignored</y>: {file_path.parent} -> {file_path.name}")
            continue

        paths_list.append(file_path)

    files_count = len(paths_list)
    logger.info(f"found {files_count} files to process")

    for i, file_path in enumerate(paths_list):
        if processed.exists(file_path):
            logger.debug(f"skipping file {file_path}: already processed")
            continue

        parent_dir_name = file_path.parents[0]
        if parent_dir_name != last_dir_name:
            logger.opt(colors=True).info(f"<g>new dir: {list(file_path.parts)[:-1]}</g>")

            await send_dir_name(file_path, pin=True)

            last_dir_name = parent_dir_name

        try:
            continue_execution = await process_audio_file(file_path, i + 1, files_count)
        except Exception as e:
            logger.opt(exception=e).error(f"an error occurred while processing a file: {e}")
            await app.send_message(config.telegram.chat_id, f"error while processing {file_path}: {e}")
            return  # terminate on fail

        if continue_execution is False:
            # if None is returned, do NOT exit
            logger.warning("exiting")
            return

if __name__ == '__main__':
    app.run(main())
