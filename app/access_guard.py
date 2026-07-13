from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Config

CHANNEL_JOIN_URL = "https://t.me/+IRBiBnrnNsFhNDJi"
CHECK_ACCESS_CALLBACK = "access:check"

_state_file: Path | None = None
_state: dict[str, Any] = {
    "channel_id": None,
    "requested_users": {},
}


def setup_access_guard(config: Config) -> None:
    global _state_file, _state
    _state_file = config.data_dir / "channel_access_state.json"
    _state = _load_state()


def _load_state() -> dict[str, Any]:
    default_state = {"channel_id": None, "requested_users": {}}
    if _state_file is None or not _state_file.exists():
        return default_state

    try:
        data = json.loads(_state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state
        if "requested_users" not in data or not isinstance(data["requested_users"], dict):
            data["requested_users"] = {}
        if "channel_id" not in data:
            data["channel_id"] = None
        return data
    except Exception:
        return default_state


def _save_state() -> None:
    if _state_file is None:
        return
    _state_file.parent.mkdir(parents=True, exist_ok=True)
    _state_file.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_access_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПОДАТЬ ЗАЯВКУ В КАНАЛ", url=CHANNEL_JOIN_URL)],
            [InlineKeyboardButton(text="✅ Я ПОДАЛ(А) ЗАЯВКУ", callback_data=CHECK_ACCESS_CALLBACK)],
        ]
    )


def register_join_request(chat_id: int, user_id: int) -> None:
    _state["channel_id"] = chat_id
    _state.setdefault("requested_users", {})[str(user_id)] = True
    _save_state()


def has_recorded_request(user_id: int) -> bool:
    return bool(_state.get("requested_users", {}).get(str(user_id)))


async def has_channel_access(bot: Bot, user_id: int) -> bool:
    # Если бот уже видел заявку на вступление — пускаем
    if has_recorded_request(user_id):
        return True

    # Если знаем channel_id, проверяем, вдруг пользователь уже принят в канал
    channel_id = _state.get("channel_id")
    if channel_id is None:
        return False

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except Exception:
        return False

    return member.status in {"creator", "administrator", "member"}


def start_access_text(name: str) -> str:
    return (
        f"{name}, привет!\n\n"
        "Чтобы получить планер, сначала подпишись на канал и подай заявку на вступление:\n"
        f"{CHANNEL_JOIN_URL}\n\n"
        "После этого нажми кнопку ниже. 👇"
    )


def retry_access_text() -> str:
    return (
        "Похоже, ты ещё не подал(а) заявку на вступление в канал.\n\n"
        "Сначала перейди по кнопке, отправь заявку на вступление, а потом нажми проверку ещё раз."
    )