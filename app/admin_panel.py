from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .analytics import AnalyticsService
from .config import Config

router = Router()

_analytics_service: AnalyticsService | None = None
_config: Config | None = None
_authorized_users: set[int] = set()


def setup_admin_panel(analytics_service: AnalyticsService, config: Config) -> None:
    global _analytics_service, _config
    _analytics_service = analytics_service
    _config = config


def is_admin(user_id: int) -> bool:
    return user_id in _authorized_users


def has_password() -> bool:
    return _config is not None and bool(_config.admin_password)


async def ensure_admin_message(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer(
            "У тебя нет доступа к админ-панели.\n\n"
            "Войди так: <code>/admin ТВОЙ_ПАРОЛЬ</code>"
        )
        return False
    return True


async def ensure_admin_callback(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer("Сначала войди через /admin пароль", show_alert=True)
        return False
    return True


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="🧭 Воронка", callback_data="admin:funnel")],
            [InlineKeyboardButton(text="👥 Последние пользователи", callback_data="admin:users")],
            [InlineKeyboardButton(text="📁 Выгрузить users CSV", callback_data="admin:export_users")],
            [InlineKeyboardButton(text="📝 Выгрузить events CSV", callback_data="admin:export_events")],
        ]
    )


def require_services() -> tuple[AnalyticsService, Config]:
    if _analytics_service is None or _config is None:
        raise RuntimeError("Admin panel is not initialized")
    return _analytics_service, _config


def format_summary_text(summary: dict) -> str:
    stops_text = "\n".join(
        f"• <code>{html.escape(step)}</code> — <b>{count}</b>"
        for step, count in summary["top_stops"]
    ) or "—"

    return (
        "<b>📊 Общая статистика</b>\n\n"
        f"Всего пользователей: <b>{summary['total_users']}</b>\n"
        f"Новых сегодня: <b>{summary['users_today']}</b>\n"
        f"Активных за 24 часа: <b>{summary['active_24h']}</b>\n"
        f"Команд /start: <b>{summary['total_starts']}</b>\n"
        f"Всего событий: <b>{summary['total_events']}</b>\n\n"
        f"<b>Где сейчас останавливаются:</b>\n{stops_text}"
    )


def format_funnel_text(funnel: list[tuple[str, int]]) -> str:
    lines = ["<b>🧭 Воронка / шаги</b>"]
    for step, count in funnel[:100]:
        lines.append(f"• <code>{html.escape(step)}</code> — <b>{count}</b>")
    return "\n".join(lines)


def format_user_line(user: dict) -> str:
    first_name = html.escape(user.get("first_name") or "—")
    username = html.escape(user.get("username") or "—")
    last_step = html.escape(user.get("last_step") or "—")
    return (
        f"<b>{first_name}</b> | ID: <code>{user['user_id']}</code> | @{username}\n"
        f"Шаг: <code>{last_step}</code>\n"
        f"Последняя активность: {html.escape(user.get('last_seen') or '—')}"
    )


def chunk_text(blocks: list[str], limit: int = 3500) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


@router.message(Command("admin"))
async def command_admin(message: Message) -> None:
    analytics_service, config = require_services()
    _ = analytics_service

    if not has_password():
        await message.answer("ADMIN_PASSWORD не настроен в переменных окружения.")
        return

    parts = (message.text or "").split(maxsplit=1)

    if is_admin(message.from_user.id):
        await message.answer(
            "<b>Админ-панель ПЛАНИРУЙ</b>\n\n"
            "Доступные команды:\n"
            "/stats — общая статистика\n"
            "/funnel — воронка\n"
            "/users — последние пользователи\n"
            "/user ID — карточка пользователя\n"
            "/export_users — CSV с пользователями\n"
            "/export_events — CSV с событиями\n"
            "/admin_logout — выйти из админки",
            reply_markup=admin_keyboard(),
        )
        return

    if len(parts) < 2:
        await message.answer("Войди так: <code>/admin ТВОЙ_ПАРОЛЬ</code>")
        return

    password = parts[1].strip()
    if password != config.admin_password:
        await message.answer("Неверный пароль.")
        return

    _authorized_users.add(message.from_user.id)
    await message.answer(
        "✅ Доступ к админ-панели открыт.\n\n"
        "Теперь доступны команды:\n"
        "/stats\n"
        "/funnel\n"
        "/users\n"
        "/user ID\n"
        "/export_users\n"
        "/export_events\n"
        "/admin_logout",
        reply_markup=admin_keyboard(),
    )


@router.message(Command("admin_logout"))
async def command_admin_logout(message: Message) -> None:
    _authorized_users.discard(message.from_user.id)
    await message.answer("Ты вышел из админ-панели.")


@router.message(Command("stats"))
async def command_stats(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()
    await message.answer(
        format_summary_text(analytics_service.get_summary()),
        reply_markup=admin_keyboard(),
    )


@router.message(Command("funnel"))
async def command_funnel(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()
    funnel = analytics_service.get_funnel()
    if not funnel:
        await message.answer("Пока нет данных по воронке.", reply_markup=admin_keyboard())
        return
    await message.answer(format_funnel_text(funnel), reply_markup=admin_keyboard())


@router.message(Command("users"))
async def command_users(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()

    parts = (message.text or "").split(maxsplit=1)
    limit = 20
    if len(parts) > 1 and parts[1].isdigit():
        limit = int(parts[1])

    users = analytics_service.get_recent_users(limit=limit)
    if not users:
        await message.answer("Пользователей пока нет.", reply_markup=admin_keyboard())
        return

    blocks = [f"<b>👥 Последние {min(limit, len(users))} пользователей</b>"]
    blocks.extend(format_user_line(user) for user in users)
    for chunk in chunk_text(blocks):
        await message.answer(chunk)


@router.message(Command("user"))
async def command_user(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Используй так: <code>/user 123456789</code>")
        return

    user_id = int(parts[1].strip())
    details = analytics_service.get_user_details(user_id)
    if not details:
        await message.answer("Такой пользователь не найден.")
        return

    user = details["user"]
    events = details["events"]
    lines = [
        "<b>Карточка пользователя</b>",
        f"ID: <code>{user['user_id']}</code>",
        f"Username: @{html.escape(user.get('username') or '—')}",
        f"Имя: {html.escape(user.get('first_name') or '—')}",
        f"Первый визит: {html.escape(user.get('first_seen') or '—')}",
        f"Последний визит: {html.escape(user.get('last_seen') or '—')}",
        f"Последний шаг: <code>{html.escape(user.get('last_step') or '—')}</code>",
        f"Кол-во /start: <b>{user.get('start_count') or 0}</b>",
        "",
        "<b>Последние события:</b>",
    ]
    for event in events:
        lines.append(
            f"• {html.escape(event['created_at'])} | "
            f"<code>{html.escape(event['event_type'])}</code> | "
            f"<code>{html.escape(event.get('step') or '—')}</code>"
        )

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n…"
    await message.answer(text)


@router.message(Command("export_users"))
async def command_export_users(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, config = require_services()
    export_path = analytics_service.export_users_csv(config.data_dir / "exports")
    await message.answer_document(FSInputFile(export_path), caption="CSV с пользователями")


@router.message(Command("export_events"))
async def command_export_events(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, config = require_services()
    export_path = analytics_service.export_events_csv(config.data_dir / "exports")
    await message.answer_document(FSInputFile(export_path), caption="CSV с событиями")


@router.callback_query(lambda c: c.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    analytics_service, _ = require_services()
    await callback.answer()
    await callback.message.answer(
        format_summary_text(analytics_service.get_summary()),
        reply_markup=admin_keyboard(),
    )


@router.callback_query(lambda c: c.data == "admin:funnel")
async def callback_admin_funnel(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    analytics_service, _ = require_services()
    await callback.answer()
    funnel = analytics_service.get_funnel()
    if not funnel:
        await callback.message.answer("Пока нет данных по воронке.", reply_markup=admin_keyboard())
        return
    await callback.message.answer(format_funnel_text(funnel), reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin:users")
async def callback_admin_users(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    analytics_service, _ = require_services()
    await callback.answer()
    users = analytics_service.get_recent_users(limit=20)
    if not users:
        await callback.message.answer("Пользователей пока нет.", reply_markup=admin_keyboard())
        return

    blocks = ["<b>👥 Последние 20 пользователей</b>"]
    blocks.extend(format_user_line(user) for user in users)
    for chunk in chunk_text(blocks):
        await callback.message.answer(chunk)


@router.callback_query(lambda c: c.data == "admin:export_users")
async def callback_admin_export_users(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    analytics_service, config = require_services()
    await callback.answer("Готовлю файл…")
    export_path = analytics_service.export_users_csv(config.data_dir / "exports")
    await callback.message.answer_document(FSInputFile(export_path), caption="CSV с пользователями")


@router.callback_query(lambda c: c.data == "admin:export_events")
async def callback_admin_export_events(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    analytics_service, config = require_services()
    await callback.answer("Готовлю файл…")
    export_path = analytics_service.export_events_csv(config.data_dir / "exports")
    await callback.message.answer_document(FSInputFile(export_path), caption="CSV с событиями")