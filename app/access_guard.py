from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Config

CHECK_ACCESS_CALLBACK = "access:check"

_state_file: Path | None = None
_state: dict[str, Any] = {
    "channels": [],
    "requested_users": {},
}


def setup_access_guard(config: Config) -> None:
    global _state_file, _state
    _state_file = config.data_dir / "channel_access_state.json"
    _state = _load_state()


def _default_state() -> dict[str, Any]:
    return {"channels": [], "requested_users": {}}


def _load_state() -> dict[str, Any]:
    if _state_file is None or not _state_file.exists():
        return _default_state()

    try:
        data = json.loads(_state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        if "channels" not in data or not isinstance(data["channels"], list):
            data["channels"] = []
        if "requested_users" not in data or not isinstance(data["requested_users"], dict):
            data["requested_users"] = {}
        return data
    except Exception:
        return _default_state()


def _save_state() -> None:
    if _state_file is None:
        return
    _state_file.parent.mkdir(parents=True, exist_ok=True)
    _state_file.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_required_channels() -> list[dict[str, Any]]:
    channels = _state.get("channels", [])
    return [dict(channel) for channel in channels]


def add_required_channel(invite_url: str) -> bool:
    invite_url = invite_url.strip()
    if not invite_url:
        return False

    channels = _state.setdefault("channels", [])
    for channel in channels:
        if channel.get("invite_url") == invite_url:
            return False

    channels.append(
        {
            "invite_url": invite_url,
            "channel_id": None,
            "title": None,
        }
    )
    _state.setdefault("requested_users", {}).setdefault(invite_url, {})
    _save_state()
    return True


def remove_required_channel(ref: str) -> bool:
    ref = ref.strip()
    channels = _state.setdefault("channels", [])
    if not channels:
        return False

    index_to_remove: int | None = None
    if ref.isdigit():
        idx = int(ref) - 1
        if 0 <= idx < len(channels):
            index_to_remove = idx
    else:
        for idx, channel in enumerate(channels):
            if channel.get("invite_url") == ref:
                index_to_remove = idx
                break

    if index_to_remove is None:
        return False

    removed = channels.pop(index_to_remove)
    invite_url = removed.get("invite_url")
    if invite_url:
        _state.setdefault("requested_users", {}).pop(invite_url, None)
    _save_state()
    return True


def _channel_key(channel: dict[str, Any]) -> str:
    return channel.get("invite_url", "")


def register_join_request(
    chat_id: int,
    user_id: int,
    chat_title: str | None = None,
    invite_url: str | None = None,
) -> None:
    channels = _state.setdefault("channels", [])
    if not channels:
        return

    target_channel: dict[str, Any] | None = None

    if invite_url:
        for channel in channels:
            if channel.get("invite_url") == invite_url:
                target_channel = channel
                break

    if target_channel is None:
        for channel in channels:
            if channel.get("channel_id") == chat_id:
                target_channel = channel
                break

    if target_channel is None and len(channels) == 1:
        target_channel = channels[0]

    if target_channel is None:
        return

    target_channel["channel_id"] = chat_id
    if chat_title:
        target_channel["title"] = chat_title

    key = _channel_key(target_channel)
    _state.setdefault("requested_users", {}).setdefault(key, {})[str(user_id)] = True
    _save_state()


def has_recorded_request(user_id: int, channel: dict[str, Any]) -> bool:
    key = _channel_key(channel)
    return bool(_state.get("requested_users", {}).get(key, {}).get(str(user_id)))


async def has_channel_access(bot: Bot, user_id: int) -> bool:
    channels = get_required_channels()
    if not channels:
        return True

    for channel in channels:
        if has_recorded_request(user_id, channel):
            continue

        channel_id = channel.get("channel_id")
        if channel_id is None:
            return False

        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        except Exception:
            return False

        if member.status not in {"creator", "administrator", "member"}:
            return False

    return True


def build_access_keyboard() -> InlineKeyboardMarkup:
    channels = get_required_channels()
    rows: list[list[InlineKeyboardButton]] = []

    if channels:
        for channel in channels:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="📢 ПОДПИСАТЬСЯ",
                        url=channel["invite_url"],
                    )
                ]
            )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📢 КАНАЛ ЕЩЁ НЕ НАСТРОЕН",
                    callback_data="access:no_channels",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="✅ Я ПОДПИСАЛСЯ(АСЬ)", callback_data=CHECK_ACCESS_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_access_text(name: str) -> str:
    channels = get_required_channels()
    if not channels:
        return (
            f"{name}, привет!\n\n"
            "Список обязательных каналов пока не настроен администратором. Попробуй позже."
        )

    return (
        f"{name}, привет!\n\n"
        "Чтобы получить планер, сначала подпишись на канал.\n\n"
        "После этого нажми ✅ Я ПОДПИСАЛСЯ(АСЬ)"
    )


def retry_access_text(name: str) -> str:
    return (
        f"{name}, похоже, ты ещё не подписался(ась)...\n\n"
        "Попробуй ещё раз и нажми кнопку ✅ Я ПОДПИСАЛСЯ(АСЬ)"
    )


def channels_help_text() -> str:
    channels = get_required_channels()
    if not channels:
        return (
            "<b>Каналы не настроены.</b>\n\n"
            "Добавь канал командой:\n"
            "<code>/add_channel https://t.me/+example</code>"
        )

    lines = ["<b>Обязательные каналы</b>"]
    for idx, channel in enumerate(channels, start=1):
        title = channel.get("title") or "Без названия"
        channel_id = channel.get("channel_id") or "ещё не определён"
        lines.append(
            f"{idx}. <b>{title}</b>\n"
            f"Ссылка: <code>{channel.get('invite_url')}</code>\n"
            f"ID канала: <code>{channel_id}</code>"
        )

    lines.append("")
    lines.append("Добавить канал:")
    lines.append("<code>/add_channel https://t.me/+example</code>")
    lines.append("")
    lines.append("Удалить канал:")
    lines.append("<code>/remove_channel 1</code>")
    return "\n\n".join(lines)