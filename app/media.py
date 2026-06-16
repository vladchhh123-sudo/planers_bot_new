from __future__ import annotations

from pathlib import Path
from typing import Iterable

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InputMediaPhoto


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class MediaNotFoundError(FileNotFoundError):
    pass


async def send_album(
    bot: Bot,
    chat_id: int,
    base_dir: Path,
    relative_dir: str,
    caption: str,
    specific_files: Iterable[str] | None = None,
) -> None:
    directory = (base_dir / relative_dir).resolve()
    if not directory.exists() or not directory.is_dir():
        raise MediaNotFoundError(f"Directory not found: {directory}")

    if specific_files:
        files = [directory / file_name for file_name in specific_files]
    else:
        files = sorted(file for file in directory.iterdir() if file.suffix.lower() in IMAGE_SUFFIXES)

    if not files:
        raise MediaNotFoundError(f"No images found in: {directory}")

    missing = [str(file) for file in files if not file.exists()]
    if missing:
        raise MediaNotFoundError("Missing image files: " + ", ".join(missing))

    media = []
    for index, file_path in enumerate(files):
        input_file = FSInputFile(file_path)
        if index == 0:
            media.append(InputMediaPhoto(media=input_file, caption=caption, parse_mode=ParseMode.HTML))
        else:
            media.append(InputMediaPhoto(media=input_file))

    await bot.send_media_group(chat_id=chat_id, media=media)
