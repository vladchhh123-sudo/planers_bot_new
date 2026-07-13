from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Config

logger = logging.getLogger(__name__)

# Ссылка на канал (убедись, что это ссылка-заявка)
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
    _state = load_state()


def load_state() -> dict[str, Any]:
    default_state = {"channel_id": None, "requested_users": {}}
    if _state_file is None or not _state_file.exists():
        return default_state

    try:
        data = json.loads(_state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state
        if "requested_users" not in data or not isinstance(data["requested_users"], dict):
            data["requested_users"] = {}
        return data
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        return default_state


def save_state() -> None:
    if _state_file is None:
        return
    try:
        _state_file.parent.mkdir(parents=True, exist_ok=True)
        _state_file.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def build_access_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПОДАТЬ ЗАЯВКУ В КАНАЛ", url=CHANNEL_JOIN_URL)],
            [InlineKeyboardButton(text="✅ Я ПОДАЛ(А) ЗАЯВКУ", callback_data=CHECK_ACCESS_CALLBACK)],
        ]
    )


def register_join_request(chat_id: int, user_id: int) -> None:
    """Регистрирует факт подачи заявки пользователем."""
    _state["channel_id"] = chat_id
    if "requested_users" not in _state:
        _state["requested_users"] = {}
    _state["requested_users"][str(user_id)] = True
    save_state()
    logger.info(f"Registered join request from {user_id} for channel {chat_id}")


def has_recorded_request(user_id: int) -> bool:
    """Проверяет, сохранена ли заявка пользователя в базе."""
    return bool(_state.get("requested_users", {}).get(str(user_id)))


async def has_channel_access(bot: Bot, user_id: int) -> bool:
    """
    Проверяет доступ:
    1. Если есть запись о поданной заявке.
    2. Если пользователь уже является участником/админом.
    """
    # 1. Сначала проверяем нашу базу заявок
    if has_recorded_request(user_id):
        return True

    # 2. Если в базе нет, пробуем проверить статус напрямую (если знаем ID канала)
    channel_id = _state.get("channel_id")
    if channel_id:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in {"creator", "administrator", "member"}:
                return True
        except Exception:
            pass

    return False


def start_access_text(name: str) -> str:
    return (
        f"<b>{name}, привет!</b>\n\n"
        "Чтобы получить планер, сначала подпишись на канал и подай заявку на вступление:\n"
        f"{CHANNEL_JOIN_URL}\n\n"
        "После того как нажмешь кнопку «Подать заявку» в канале, возвращайся сюда и жми кнопку ниже 👇"
    )


def retry_access_text() -> str:
    return (
        "<b>Ты не подписался, попробуй еще раз!</b> ❌\n\n"
        "Похоже, ты ещё не подал(а) заявку на вступление в канал.\n"
        "Сначала перейди по кнопке выше, отправь заявку, а затем нажми проверку."
    )