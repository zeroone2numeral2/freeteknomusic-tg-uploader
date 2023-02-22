import base64
import io
import json
import os
from pathlib import Path
import datetime
from typing import Optional, Union, List

import eyed3
from eyed3.mp3 import Mp3AudioFile

import utilities as utilities
from config import config

logger = utilities.get_logger(__file__)


def main():
    tracks_path = Path(config.tracks.path)
    allowed_extensions = tuple(config.tracks.allowed_extensions)
    logger.info(f"allowed extensions: {allowed_extensions}")
    data = []
    for file_path in tracks_path.rglob("*"):
        if file_path.is_dir():
            continue

        if not file_path.name.lower().endswith(allowed_extensions):
            logger.opt(colors=True).info(f"<y>file ignored: invalid extension</y>: {file_path.parent} -> {file_path.name}")
            continue

        audio_data = {
            "file_path": file_path.parts[config.tracks.remove_first_n_directories_from_path:],
            "metadata": dict()
        }

        try:
            audio_file: Optional[Mp3AudioFile] = eyed3.load(file_path)
        except UnicodeDecodeError:
            # must investigate
            logger.warning(f"UnicodeDecodeError while decoding metadata for file {file_path}")
            data.append(audio_data)
            continue

        if not audio_file:
            logger.warning(f"loading tags returned None for file {file_path}")
            data.append(audio_data)
            continue

        metadata = dict()
        if audio_file.info:
            metadata["time_secs"] = audio_file.info.time_secs
            metadata["size_bytes"] = audio_file.info.size_bytes

        if audio_file.tag:
            metadata["title"] = audio_file.tag.title
            metadata["artist"] = audio_file.tag.artist
            metadata["album"] = audio_file.tag.album
            metadata["album_artist"] = audio_file.tag.album_artist
            metadata["album_type"] = audio_file.tag.album_type
            metadata["genre"] = audio_file.tag.genre.name if audio_file.tag.genre else None
            metadata["composer"] = audio_file.tag.composer
            metadata["disc_num"] = audio_file.tag.disc_num
            metadata["release_date"] = str(audio_file.tag.release_date) if audio_file.tag.release_date else None
            metadata["original_release_date"] = str(audio_file.tag.original_release_date) if audio_file.tag.original_release_date else None
            metadata["recording_date"] = str(audio_file.tag.recording_date) if audio_file.tag.recording_date else None

            metadata["artworks"] = []
            if config.script_metadata_to_json.include_base64_artwork_string and audio_file.tag.images:
                for image in audio_file.tag.images:
                    artwork_mem = io.BytesIO(image.image_data)
                    artwork_mem.seek(0)
                    img_bytes = artwork_mem.read()

                    base64_encoded_result_bytes = base64.b64encode(img_bytes)
                    base64_encoded_result_str = base64_encoded_result_bytes.decode('ascii')
                    metadata["artworks"].append(base64_encoded_result_str)

        audio_data["metadata"] = metadata
        data.append(audio_data)

    with open("data/files-metadata.json", "w+") as f:
        json.dump(data, f, indent=2)


if __name__ == '__main__':
    main()
