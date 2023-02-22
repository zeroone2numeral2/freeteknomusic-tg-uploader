import sys
import os
import json
from pathlib import Path
from typing import Union, Optional, List, Tuple

from loguru import logger


def get_logger(file_name):
    file_name = os.path.basename(file_name).replace('.py', '')

    logger.remove()
    logger.add(f"logs/{file_name}" + "_{time:YYYYMMDD_HHmmss}.log")
    logger.add(
        sys.stdout,
        level="INFO",
        colorize=True,
        format="<green>{time:YYYYMMDD HH:mm:ss:SSS}</green> {level} <level>{message}</level>",
        backtrace=True,
        diagnose=True
    )

    return logger


def human_readable_size(size, precision=2):
    suffixes = ['b', 'kb', 'mb', 'gb', 'tb']
    suffix_index = 0
    while size > 1024 and suffix_index < 4:
        suffix_index += 1  # increment the index of the suffix
        size = size / 1024.0

    string = '%.*f %s' % (precision, size, suffixes[suffix_index])

    return string.replace(".00", "")  # always trim final ".00"


class Storage:
    def __init__(self, file_path, init_object, autosave=False):
        self._file_path = os.path.normpath(file_path)
        self._autosave = autosave

        try:
            with open(self._file_path, 'r') as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = init_object
            self.dump()

    def dump(self):
        with open(self._file_path, 'w+') as f:
            json.dump(self._data, f, indent=4)


class StorageList(Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._path_split = "..."

    def convert_path(self, p: Path):
        return self._path_split.join(p.parts)

    def add(self, p: Path, save=False, skip_duplicates=True):
        item = self.convert_path(p)

        if skip_duplicates and item in self._data:
            return False

        self._data.append(item)

        if save or self._autosave:
            self.dump()

        return True

    def exists(self, p: Path):
        item = self.convert_path(p)

        return item in self._data


class StoragMessages(Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, init_object={}, **kwargs)
        self._path_split = "..."

    def convert_path(self, p: Path):
        return self._path_split.join(p.parts)

    def add(self, message_id: int, value: Union[Path, str], override_if_existing=True, save=False):
        message_id = str(message_id)

        if message_id in self._data and not override_if_existing:
            return False

        text = None
        origin_audio_path: Optional[Tuple] = None

        if isinstance(value, Path):
            origin_audio_path = value.parts
        else:
            text = value

        self._data[message_id] = dict(
            text=text,
            origin_audio_path=origin_audio_path
        )

        if save or self._autosave:
            self.dump()

        return True

    def exists(self, message_id: int):
        message_id = str(message_id)

        return message_id in self._data

