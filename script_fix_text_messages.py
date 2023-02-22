import io
import os
import asyncio
import json
from typing import Optional
from typing import TypedDict

from pyrogram import Client
from pyrogram.errors import FloodWait

import utilities as utilities
from config import config

logger = utilities.get_logger(__file__)


user = Client(
    **config.pyrogram,
    name=config.script_fix_text_messages.name,
    phone_number=config.script_fix_text_messages.phone_number,
    workers=1,
    no_updates=True
)
user.start()


class Storage:
    def __init__(self, file_path, autosave=False):
        self._file_path = os.path.normpath(file_path)
        self._autosave = autosave

        try:
            with open(self._file_path, 'r') as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = {}
            self.dump()

    def dump(self):
        with open(self._file_path, 'w+') as f:
            json.dump(self._data, f, indent=4)

    def add(self, message_id: int, text: str, save=False, override_if_existing=True):
        message_id = str(message_id)

        if message_id in self._data and not override_if_existing:
            return False

        self._data[message_id] = text

        if save or self._autosave:
            self.dump()

        return True

    def exists(self, message_id: int):
        message_id = str(message_id)

        return message_id in self._data


text_messages_storage = Storage("data/text-messages.json", autosave=True)


async def main():
    messages_pinning_cooldown = 90  # 90 seconds is the min time to sleep to avoid to be rate-limited
    async for message in user.get_chat_history(config.telegram.chat_id):
        if not message.text:
            continue

        text_messages_storage.add(message.id, message.text)

        if not message.text.startswith("/media/chemp/Volume/jungle/"):
            continue

        path_str = message.text.replace("/media/chemp/Volume/jungle/", "")
        path_list = path_str.split("/")
        new_text = " -> ".join(path_list)

        retry = True
        while retry:
            try:
                logger.info(f"editing message {message.id} ({message.text})...")
                await message.edit_text(new_text, disable_web_page_preview=True)

                retry = False
            except FloodWait as e:
                logger.opt(colors=True).info(f"<r>flood_wait while editing: will retry in {e.value} seconds</r>")
                await asyncio.sleep(e.value + 180)

            try:
                logger.info(f"pinning message {message.id} and sleeping for {messages_pinning_cooldown} seconds...")
                service_message = await message.pin(disable_notification=True)
                await service_message.delete()
            except FloodWait as e:
                logger.opt(colors=True).info(f"<r>flood_wait while pinning: will retry in {e.value} seconds</r>")
                await asyncio.sleep(e.value + 5)

            await asyncio.sleep(messages_pinning_cooldown + 1)


if __name__ == '__main__':
    user.run(main())
