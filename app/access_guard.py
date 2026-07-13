from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Config

logger = logging.getLogger(__name__)

# ТВОЯ ССЫЛКА НА КАНАЛ (Должна быть ссылкой с заявкой на вступление)
CHANNEL_JOIN_URL = "https://t.me/+IRBiBnrnNsFhNDJi"
CHECK_ACCESS_CALLBACK = "access:check"

_state_file: Path | None = None
_state: dict[str, Any] = {
    "channel_id": None,
    "requested_users": {},
}


def setup_access_guard(config: Config) -> None:
    """Инициализация пути к файлу состояния и загрузка данных."""
    global _state_file, _state
    # Файл будет лежать в папке data вашего проекта
    _state_file = config.data_dir / "channel_access_state.json"
    _state = load_state()


def load_state() -> dict[str, Any]:
    """Загрузка состояния из JSON файла."""
    default_state = {"channel_id": None, "requested_users": {}}
    if _state_file is None or not _state_file.exists():
        return default_state

    try:
        data = json.loads(_state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state
        # Гарантируем наличие ключей
        if "requested_users" not in data or not isinstance(data["requested_users"], dict):
            data["requested_users"] = {}
        if "channel_id" not in data:
            data["channel_id"] = None
        return data
    except Exception as e:
        logger.error(f"Ошибка при загрузке состояния доступа: {e}")
        return default_state


def save_state() -> None:
    """Сохранение текущего состояния в JSON файл."""
    if _state_file is None:
        return
    try:
        _state_file.parent.mkdir(parents=True, exist_ok=True)
        _state_file.write_text(
            json.dumps(_state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении состояния доступа: {e}")


def build_access_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой подписки и проверки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПОДАТЬ ЗАЯВКУ В КАНАЛ", url=CHANNEL_JOIN_URL)],
            [InlineKeyboardButton(text="✅ Я ПОДАЛ(А) ЗАЯВКУ", callback_data=CHECK_ACCESS_CALLBACK)],
        ]
    )


def register_join_request(chat_id: int, user_id: int) -> None:
    """Регистрирует ID канала и факт подачи заявки пользователем."""
    _state["channel_id"] = chat_id
    if "requested_users" not in _state:
        _state["requested_users"] = {}

    _state["requested_users"][str(user_id)] = True
    save_state()
    logger.info(f"Заявка от пользователя {user_id} в канал {chat_id} зафиксирована.")


def has_recorded_request(user_id: int) -> bool:
    """Проверяет, есть ли запись о поданной заявке в нашей локальной базе."""
    requested = _state.get("requested_users", {})
    return bool(requested.get(str(user_id)))


async def has_channel_access(bot: Bot, user_id: int) -> bool:
    """
    Главная функция проверки доступа.
    Проверяет:
    1. Подавал ли пользователь заявку (через нашу базу).
    2. Является ли пользователь уже участником канала (через API Telegram).
    """
    # 1. Если в базе есть отметка о заявке — пускаем
    if has_recorded_request(user_id):
        return True

    # 2. Если в базе нет, но мы знаем ID канала, проверяем статус напрямую
    channel_id = _state.get("channel_id")
    if channel_id is not None:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            # Статусы, которые считаются "подписанными"
            if member.status in {"creator", "administrator", "member"}:
                return True
        except Exception:
            # Если бот не админ или канал не найден, игнорируем ошибку
            pass

    return False


def start_access_text(name: str) -> str:
    """Текст для первой попытки входа (команда /start)."""
    return (
        f"<b>{name}, привет!</b>\n\n"
        "Чтобы получить планер, сначала подпишись на канал и подай заявку на вступление:\n"
        f"{CHANNEL_JOIN_URL}\n\n"
        "После того как нажмешь кнопку <b>«Подать заявку»</b> в канале, возвращайся сюда и жми кнопку ниже 👇"
    )


def retry_access_text() -> str:
    """Текст, если пользователь нажал проверку, но заявку не подал."""
    return (
        "<b>Ты не подписался, попробуй еще раз!</b> ❌\n\n"
        "Похоже, ты ещё не подал(а) заявку на вступление в канал.\n\n"
        "Сначала перейди по кнопке выше, отправь заявку на вступление, "
        "а потом нажми проверку ещё раз."
    )