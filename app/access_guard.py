from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ИМПОРТ БЕЗ ТОЧКИ
from config import Config

logger = logging.getLogger(__name__)

CHANNEL_JOIN_URL = "https://t.me/+IRBiBnrnNsFhNDJi"
CHECK_ACCESS_CALLBACK = "access:check"

_state_file: Path | None = None
_state: dict[str, Any] = {"channel_id": None, "requested_users": {}}

def setup_access_guard(config: Config) -> None:
    global _state_file, _state
    _state_file = Path(config.data_dir) / "channel_access_state.json"
    if _state_file.exists():
        try:
            _state = json.loads(_state_file.read_text(encoding="utf-8"))
        except Exception:
            _state = {"channel_id": None, "requested_users": {}}

def save_state() -> None:
    if _state_file:
        _state_file.parent.mkdir(parents=True, exist_ok=True)
        _state_file.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")

def register_join_request(chat_id: int, user_id: int) -> None:
    _state["channel_id"] = chat_id
    if "requested_users" not in _state:
        _state["requested_users"] = {}
    _state["requested_users"][str(user_id)] = True
    save_state()

async def has_channel_access(bot: Bot, user_id: int) -> bool:
    # 1. Проверка по сохраненным заявкам
    if str(user_id) in _state.get("requested_users", {}):
        return True
    # 2. Проверка статуса в канале
    channel_id = _state.get("channel_id")
    if channel_id:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ("member", "administrator", "creator"):
                return True
        except Exception:
            pass
    return False

def build_access_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 ПОДАТЬ ЗАЯВКУ В КАНАЛ", url=CHANNEL_JOIN_URL)],
        [InlineKeyboardButton(text="✅ Я ПОДАЛ(А) ЗАЯВКУ", callback_data=CHECK_ACCESS_CALLBACK)]
    ])

def start_access_text(name: str) -> str:
    return (
        f"<b>{name}, привет!</b>\n\n"
        f"Чтобы получить планер, сначала подпишись на канал и подай заявку на вступление:\n"
        f"{CHANNEL_JOIN_URL}\n\n"
        "После этого нажми кнопку ниже. 👇"
    )

def retry_access_text() -> str:
    return (
        "<b>Ты не подписался, попробуй еще раз!</b> ❌\n\n"
        "Похоже, ты ещё не подал(а) заявку на вступление в канал.\n"
        "Сначала подай заявку, а потом нажми проверку."
    )