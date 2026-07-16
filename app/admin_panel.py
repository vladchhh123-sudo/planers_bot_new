from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .access_guard import (
    add_required_channel,
    channels_help_text,
    remove_required_channel,
)
from .analytics import AnalyticsService
from .config import Config

router = Router()
logger = logging.getLogger(__name__)

_analytics_service: AnalyticsService | None = None
_config: Config | None = None
_authorized_users: set[int] = set()
_notify_enabled_users: set[int] = set()
_notify_state_file: Path | None = None
_pending_support_users: set[int] = set()
_pending_admin_auth_users: set[int] = set()

PRODUCT_NAMES = {
    "habits": "Планер привычек",
    "tasks": "Планер задач",
    "finance": "Планер финансов",
    "goals": "Планер целей",
    "awareness": "Дневник осознанности",
}

BUNDLE_NAMES = {
    "productivity": "Набор «Продуктивность»",
    "balance": "Набор «Жизнь по балансу»",
    "ecosystem": "Набор «Экосистема роста»",
}

COLOR_NAMES = {
    "white": "белый",
    "black": "чёрный",
    "green": "зелёный",
    "burgundy": "бордовый",
    "blue": "синий",
    "pink": "розовый",
    "beige": "бежевый",
    "violet": "фиолетовый",
    "gray": "серый",
}

SEGMENT_ALIASES = {
    "start": ("start_screen", "Открыли стартовое сообщение"),
    "catalog": ("catalog_menu", "Дошли до сообщения со всеми планерами"),
    "habits": ("product_habits_card", "Дошли до планера привычек"),
    "tasks": ("product_tasks_card", "Дошли до планера задач"),
    "finance": ("product_finance_card", "Дошли до планера финансов"),
    "goals": ("product_goals_card", "Дошли до планера целей"),
    "awareness": ("product_awareness_card", "Дошли до дневника осознанности"),
    "offer": ("offer_channel_plus", "Дошли до предложения с наборами"),
    "single": ("offer_take_single", "Выбрали вариант «Пока что возьму планер»"),
    "planner_menu": ("offer_single_planner_menu", "Дошли до меню выбора одного планера"),
    "bundles": ("bundles_landing", "Дошли до наборов"),
    "productivity": ("bundle_productivity_card", "Открыли набор «Продуктивность»"),
    "balance": ("bundle_balance_card", "Открыли набор «Жизнь по балансу»"),
    "ecosystem": ("bundle_ecosystem_card", "Открыли набор «Экосистема роста»"),
}


def setup_admin_panel(analytics_service: AnalyticsService, config: Config) -> None:
    global _analytics_service, _config, _notify_state_file, _notify_enabled_users
    _analytics_service = analytics_service
    _config = config
    _notify_state_file = config.data_dir / "admin_notify.json"
    _notify_enabled_users = _load_notify_users()


def _load_notify_users() -> set[int]:
    if _notify_state_file is None or not _notify_state_file.exists():
        return set()

    try:
        data = json.loads(_notify_state_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {int(item) for item in data if str(item).isdigit()}
    except Exception:
        return set()

    return set()


def _save_notify_users() -> None:
    if _notify_state_file is None:
        return
    _notify_state_file.parent.mkdir(parents=True, exist_ok=True)
    _notify_state_file.write_text(
        json.dumps(sorted(_notify_enabled_users), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_admin(user_id: int) -> bool:
    return user_id in _authorized_users


def has_password() -> bool:
    return _config is not None and bool(_config.admin_password)


def notifications_enabled_for(user_id: int) -> bool:
    return user_id in _notify_enabled_users


def get_admin_recipients() -> set[int]:
    return set(_authorized_users) | set(_notify_enabled_users)


async def notify_admins_about_start(bot: Bot, user: Any) -> None:
    if not _notify_enabled_users:
        return

    user_id = int(user.id)
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None) or "Без имени"

    username_text = f"@{html.escape(username)}" if username else "без username"
    first_name_text = html.escape(first_name)

    text = (
        "<b>🔔 Новый вход в бота</b>\n\n"
        f"Имя: <b>{first_name_text}</b>\n"
        f"Username: {username_text}\n"
        f"ID: <code>{user_id}</code>"
    )

    for admin_id in list(_notify_enabled_users):
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            continue


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
        try:
            await callback.answer("Сначала войди через /admin пароль", show_alert=True)
        except TelegramBadRequest:
            pass
        return False
    return True


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="🧭 Воронка", callback_data="admin:funnel")],
            [InlineKeyboardButton(text="👥 Последние пользователи", callback_data="admin:users")],
            [InlineKeyboardButton(text="🎯 Сегменты", callback_data="admin:segments")],
            [InlineKeyboardButton(text="📢 Каналы", callback_data="admin:channels")],
            [InlineKeyboardButton(text="✉️ Рассылка", callback_data="admin:send")],
            [
                InlineKeyboardButton(text="🔔 Включить уведомления", callback_data="admin:notify_on"),
                InlineKeyboardButton(text="🔕 Выключить уведомления", callback_data="admin:notify_off"),
            ],
            [InlineKeyboardButton(text="📁 Выгрузить users CSV", callback_data="admin:export_users")],
            [InlineKeyboardButton(text="📝 Выгрузить events CSV", callback_data="admin:export_events")],
        ]
    )


def require_services() -> tuple[AnalyticsService, Config]:
    if _analytics_service is None or _config is None:
        raise RuntimeError("Admin panel is not initialized")
    return _analytics_service, _config


def build_admin_help_text() -> str:
    return (
        "<b>Админ-панель ПЛАНИРУЙ</b>\n\n"
        "Доступные команды:\n"
        "/stats — общая статистика\n"
        "/funnel — воронка\n"
        "/users — последние пользователи\n"
        "/user ID_ИЛИ_@username — карточка пользователя\n"
        "/segment alias — список пользователей по шагу\n"
        "/channels — список обязательных каналов\n"
        "/add_channel ссылка — добавить канал\n"
        "/remove_channel номер — удалить канал\n"
        "/send получатели | текст — рассылка по ID/username\n"
        "/send_segment alias | текст — рассылка по сегменту\n"
        "/support_answer ID_ИЛИ_@username | текст — ответ на обращение\n"
        "/reset_nurture ID_ИЛИ_@username — сбросить прогрев\n"
        "/notify_on — включить уведомления о новых входах\n"
        "/notify_off — выключить уведомления о новых входах\n"
        "/export_users — CSV с пользователями\n"
        "/export_events — CSV с событиями\n"
        "/admin_logout — выйти из админки"
    )


def humanize_step(step: str | None) -> str:
    if not step:
        return "Неизвестный шаг"

    if step == "start_screen":
        return "Стартовое сообщение"
    if step == "catalog_menu":
        return "Сообщение со всеми планерами"
    if step == "offer_channel_plus":
        return "Дошли до предложения с наборами"
    if step == "offer_take_single":
        return "Выбрали «Пока что возьму планер»"
    if step == "offer_single_planner_menu":
        return "Меню выбора одного планера"
    if step == "bundles_landing":
        return "Экран с наборами"
    if step == "pay_channel_offer":
        return "Переход к оплате набора"

    if step.startswith("product_") and step.endswith("_card"):
        product_id = step[len("product_") : -len("_card")]
        return f"Открыли карточку: {PRODUCT_NAMES.get(product_id, product_id)}"

    if step.startswith("colors_product_"):
        product_id = step[len("colors_product_") :]
        return f"Дошли до выбора цвета: {PRODUCT_NAMES.get(product_id, product_id)}"

    if step.startswith("after_color_"):
        rest = step[len("after_color_") :]
        if "_" in rest:
            product_id, color_id = rest.rsplit("_", 1)
            return (
                f"Выбрали цвет «{COLOR_NAMES.get(color_id, color_id)}» "
                f"для {PRODUCT_NAMES.get(product_id, product_id)}"
            )

    if step.startswith("pay_product_"):
        rest = step[len("pay_product_") :]
        if "_" in rest:
            product_id, color_id = rest.rsplit("_", 1)
            return (
                f"Дошли до оплаты {PRODUCT_NAMES.get(product_id, product_id)} "
                f"({COLOR_NAMES.get(color_id, color_id)})"
            )

    if step.startswith("bundle_") and step.endswith("_card"):
        bundle_id = step[len("bundle_") : -len("_card")]
        return f"Открыли карточку: {BUNDLE_NAMES.get(bundle_id, bundle_id)}"

    if step.startswith("pay_bundle_"):
        rest = step[len("pay_bundle_") :]
        if "_" in rest:
            bundle_id, color_id = rest.rsplit("_", 1)
            return (
                f"Дошли до оплаты {BUNDLE_NAMES.get(bundle_id, bundle_id)} "
                f"({COLOR_NAMES.get(color_id, color_id)})"
            )

    return step


def format_summary_text(summary: dict) -> str:
    stops_text = "\n".join(
        f"• {html.escape(humanize_step(step))} — <b>{count}</b>"
        for step, count in summary["top_stops"]
    ) or "—"

    return (
        "<b>📊 Общая статистика</b>\n\n"
        f"Всего пользователей: <b>{summary['total_users']}</b>\n"
        f"Активных пользователей: <b>{summary['active_users']}</b>\n"
        f"Неактивных пользователей: <b>{summary['inactive_users']}</b>\n"
        f"Новых сегодня: <b>{summary['users_today']}</b>\n"
        f"Активных за 24 часа: <b>{summary['active_24h']}</b>\n"
        f"Команд /start: <b>{summary['total_starts']}</b>\n"
        f"Всего событий: <b>{summary['total_events']}</b>\n\n"
        f"<b>Где сейчас останавливаются:</b>\n{stops_text}"
    )


def format_funnel_text(funnel: list[tuple[str, int]]) -> str:
    lines = ["<b>🧭 Воронка по шагам</b>"]
    for step, count in funnel[:100]:
        lines.append(f"• {html.escape(humanize_step(step))} — <b>{count}</b>")
    return "\n".join(lines)


def format_user_line(user: dict) -> str:
    first_name = html.escape(user.get("first_name") or "—")
    username = html.escape(user.get("username") or "—")
    last_step = html.escape(humanize_step(user.get("last_step")))
    status = "неактивен" if user.get("bot_blocked") else "активен"
    return (
        f"<b>{first_name}</b> | ID: <code>{user['user_id']}</code> | @{username}\n"
        f"Статус: {status}\n"
        f"Последний шаг: {last_step}\n"
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


def mailing_help_text() -> str:
    return (
        "<b>✉️ Рассылка выбранным пользователям</b>\n\n"
        "Команда по ID и username:\n"
        "<code>/send 123456789,@username1,@username2 | Текст сообщения</code>\n\n"
        "Команда для всех пользователей:\n"
        "<code>/send all | Текст сообщения</code>\n\n"
        "Команда по сегменту:\n"
        "<code>/send_segment finance | Текст сообщения</code>\n\n"
        "Примеры сегментов:\n"
        "• <code>catalog</code> — дошли до всех планеров\n"
        "• <code>finance</code> — дошли до планера финансов\n"
        "• <code>tasks</code> — дошли до планера задач\n"
        "• <code>habits</code> — дошли до планера привычек\n"
        "• <code>goals</code> — дошли до планера целей\n"
        "• <code>awareness</code> — дошли до дневника осознанности\n"
        "• <code>offer</code> — дошли до предложения с наборами\n"
        "• <code>bundles</code> — дошли до наборов"
    )


def segments_help_text() -> str:
    lines = ["<b>🎯 Сегменты пользователей по воронке</b>"]
    for alias, (_, description) in SEGMENT_ALIASES.items():
        lines.append(f"• <code>{alias}</code> — {html.escape(description)}")
    lines.append("")
    lines.append("Посмотреть пользователей сегмента:")
    lines.append("<code>/segment finance</code>")
    lines.append("")
    lines.append("Сделать рассылку сегменту:")
    lines.append("<code>/send_segment finance | Текст сообщения</code>")
    return "\n".join(lines)


def parse_send_command(text: str) -> tuple[list[str], str] | None:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None

    body = parts[1].strip()
    if "|" not in body:
        return None

    raw_targets, raw_message = body.split("|", maxsplit=1)
    raw_targets = raw_targets.strip()
    raw_message = raw_message.strip()

    if not raw_targets or not raw_message:
        return None

    targets = [item.strip() for item in re.split(r"[,\s]+", raw_targets) if item.strip()]
    if not targets:
        return None

    return targets, raw_message


def parse_segment_command(text: str) -> tuple[str, str] | None:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None

    body = parts[1].strip()
    if "|" not in body:
        return None

    raw_alias, raw_message = body.split("|", maxsplit=1)
    alias = raw_alias.strip().lower()
    outgoing_text = raw_message.strip()
    if not alias or not outgoing_text:
        return None
    return alias, outgoing_text


def get_segment(alias: str) -> tuple[str, str] | None:
    return SEGMENT_ALIASES.get(alias.lower())


def build_support_prompt(name: str) -> str:
    return f"{name}, напиши свой вопрос."


def build_support_success() -> str:
    return "Мы уже занимаемся твоим вопросом и дадим ответ в течение 24 часов."


async def notify_admins_about_support(bot: Bot, user: Any, support_text: str) -> None:
    recipients = get_admin_recipients()
    if not recipients:
        logger.warning("Support message received, but no admin recipients are currently available")
        return

    user_id = int(user.id)
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None) or "Без имени"

    username_text = f"@{html.escape(username)}" if username else "без username"
    first_name_text = html.escape(first_name)
    safe_support_text = html.escape(support_text)

    text = (
        "<b>⚠️ Новое обращение</b>\n\n"
        f"Имя: <b>{first_name_text}</b>\n"
        f"Username: {username_text}\n"
        f"ID: <code>{user_id}</code>\n\n"
        f"<b>Текст обращения:</b>\n{safe_support_text}"
    )

    for admin_id in recipients:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            logger.exception("Не удалось отправить обращение админу %s", admin_id)


@router.message(Command("support"))
async def command_support(message: Message) -> None:
    name = html.escape(getattr(message.from_user, "first_name", None) or "друг")
    _pending_support_users.add(message.from_user.id)
    await message.answer(build_support_prompt(name))


@router.message(lambda message: message.from_user is not None and message.from_user.id in _pending_support_users)
async def handle_support_message(message: Message) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Пожалуйста, отправь сообщение обычным текстом.")
        return

    _pending_support_users.discard(message.from_user.id)
    await notify_admins_about_support(message.bot, message.from_user, message.text)
    await message.answer(build_support_success())


@router.message(Command("support_answer"))
async def command_support_answer(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    body = (message.text or "").split(maxsplit=1)
    if len(body) < 2 or "|" not in body[1]:
        await message.answer(
            "Используй так: <code>/support_answer 123456789 | Текст ответа</code>\n"
            "или <code>/support_answer @username | Текст ответа</code>"
        )
        return

    target_raw, reply_text = body[1].split("|", maxsplit=1)
    target_raw = target_raw.strip()
    reply_text = reply_text.strip()

    if not target_raw or not reply_text:
        await message.answer(
            "Используй так: <code>/support_answer 123456789 | Текст ответа</code>\n"
            "или <code>/support_answer @username | Текст ответа</code>"
        )
        return

    analytics_service, _ = require_services()
    users, unresolved = analytics_service.find_users_by_refs([target_raw])
    if not users:
        unresolved_text = ", ".join(unresolved) if unresolved else target_raw
        await message.answer(f"Не удалось найти пользователя: <code>{html.escape(unresolved_text)}</code>")
        return

    user = users[0]
    target_id = user["user_id"]

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=f"<b>Ответ поддержки</b>\n\n{html.escape(reply_text)}",
        )
        await message.answer(f"✅ Ответ отправлен пользователю <code>{target_id}</code>")
    except Exception as exc:
        await message.answer(
            f"Не удалось отправить ответ пользователю <code>{target_id}</code>\n\n"
            f"Ошибка: <code>{html.escape(str(exc))}</code>"
        )


async def send_message_to_users(
    message: Message,
    users: list[dict],
    outgoing_text: str,
    unresolved: list[str] | None = None,
) -> None:
    analytics_service, _ = require_services()
    sent_count = 0
    failed: list[str] = []

    for user in users:
        try:
            await message.bot.send_message(chat_id=user["user_id"], text=outgoing_text)
            analytics_service.mark_user_blocked(user["user_id"], False)
            sent_count += 1
        except Exception as exc:
            error_text = str(exc)
            if "bot was blocked by the user" in error_text.lower() or "forbidden" in error_text.lower():
                analytics_service.mark_user_blocked(user["user_id"], True)
            username = user.get("username") or "—"
            failed.append(f"{user['user_id']} (@{username}): {error_text}")

    report_lines = [
        "<b>Результат рассылки</b>",
        f"Найдено получателей: <b>{len(users)}</b>",
        f"Успешно отправлено: <b>{sent_count}</b>",
    ]

    if unresolved:
        report_lines.append("")
        report_lines.append("<b>Не найдены в базе:</b>")
        for item in unresolved:
            report_lines.append(f"• <code>{html.escape(item)}</code>")

    if failed:
        report_lines.append("")
        report_lines.append("<b>Ошибки доставки:</b>")
        for item in failed[:20]:
            report_lines.append(f"• {html.escape(item)}")
        if len(failed) > 20:
            report_lines.append(f"• И ещё {len(failed) - 20} ошибок")

    await message.answer("\n".join(report_lines), reply_markup=admin_keyboard())


@router.message(Command("admin"))
async def command_admin(message: Message) -> None:
    _, config = require_services()

    if not has_password():
        await message.answer("ADMIN_PASSWORD не настроен в переменных окружения.")
        return

    parts = (message.text or "").split(maxsplit=1)

    if is_admin(message.from_user.id):
        await message.answer(build_admin_help_text(), reply_markup=admin_keyboard())
        return

    if len(parts) < 2:
        _pending_admin_auth_users.add(message.from_user.id)
        await message.answer("Введи пароль следующим сообщением или используй формат <code>/admin ТВОЙ_ПАРОЛЬ</code>")
        return

    password = parts[1].strip()
    if password != config.admin_password:
        await message.answer("Неверный пароль.")
        return

    _authorized_users.add(message.from_user.id)
    _pending_admin_auth_users.discard(message.from_user.id)
    await message.answer(
        "✅ Доступ к админ-панели открыт.\n\n" + build_admin_help_text(),
        reply_markup=admin_keyboard(),
    )


@router.message(lambda message: message.from_user is not None and message.from_user.id in _pending_admin_auth_users)
async def handle_admin_password(message: Message) -> None:
    _, config = require_services()

    if not message.text or message.text.startswith("/"):
        await message.answer("Пожалуйста, отправь пароль обычным текстом.")
        return

    password = message.text.strip()
    if password != config.admin_password:
        await message.answer("Неверный пароль. Попробуй ещё раз или снова используй /admin")
        return

    _authorized_users.add(message.from_user.id)
    _pending_admin_auth_users.discard(message.from_user.id)
    await message.answer(
        "✅ Доступ к админ-панели открыт.\n\n" + build_admin_help_text(),
        reply_markup=admin_keyboard(),
    )


@router.message(Command("admin_logout"))
async def command_admin_logout(message: Message) -> None:
    _authorized_users.discard(message.from_user.id)
    _pending_admin_auth_users.discard(message.from_user.id)
    await message.answer("Ты вышел из админ-панели.")


@router.message(Command("notify_on"))
async def command_notify_on(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    _notify_enabled_users.add(message.from_user.id)
    _save_notify_users()
    await message.answer(
        "✅ Уведомления о новых входах в бота включены.",
        reply_markup=admin_keyboard(),
    )


@router.message(Command("notify_off"))
async def command_notify_off(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    _notify_enabled_users.discard(message.from_user.id)
    _save_notify_users()
    await message.answer(
        "🔕 Уведомления о новых входах в бота выключены.",
        reply_markup=admin_keyboard(),
    )


@router.message(Command("stats"))
async def command_stats(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()
    await message.answer(format_summary_text(analytics_service.get_summary()), reply_markup=admin_keyboard())


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
    if len(parts) < 2:
        await message.answer("Используй так: <code>/user 123456789</code> или <code>/user @username</code>")
        return

    details = analytics_service.get_user_details(parts[1].strip())
    if not details:
        await message.answer("Такой пользователь не найден.")
        return

    user = details["user"]
    events = details["events"]
    status = "неактивен" if user.get("bot_blocked") else "активен"
    lines = [
        "<b>Карточка пользователя</b>",
        f"ID: <code>{user['user_id']}</code>",
        f"Username: @{html.escape(user.get('username') or '—')}",
        f"Имя: {html.escape(user.get('first_name') or '—')}",
        f"Статус: {status}",
        f"Первый визит: {html.escape(user.get('first_seen') or '—')}",
        f"Последний визит: {html.escape(user.get('last_seen') or '—')}",
        f"Последний шаг: {html.escape(humanize_step(user.get('last_step')))}",
        f"Кол-во /start: <b>{user.get('start_count') or 0}</b>",
        "",
        "<b>Последние события:</b>",
    ]
    for event in events:
        lines.append(
            f"• {html.escape(event['created_at'])} | "
            f"<code>{html.escape(event['event_type'])}</code> | "
            f"{html.escape(humanize_step(event.get('step')))}"
        )

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n…"
    await message.answer(text)


@router.message(Command("segment"))
async def command_segment(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(segments_help_text(), reply_markup=admin_keyboard())
        return

    alias = parts[1].strip().lower()
    segment = get_segment(alias)
    if segment is None:
        await message.answer("Неизвестный сегмент.\n\n" + segments_help_text(), reply_markup=admin_keyboard())
        return

    step, description = segment
    users = analytics_service.get_users_by_step(step, limit=500)
    if not users:
        await message.answer(f"По сегменту «{html.escape(alias)}» пользователей пока нет.", reply_markup=admin_keyboard())
        return

    blocks = [f"<b>{html.escape(description)}</b>\nВсего: <b>{len(users)}</b>"]
    blocks.extend(format_user_line(user) for user in users)
    for chunk in chunk_text(blocks):
        await message.answer(chunk)


@router.message(Command("channels"))
@router.message(F.text.regexp(r"^/channels(?:@\w+)?$"))
async def command_channels(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    await message.answer(channels_help_text(), reply_markup=admin_keyboard())


@router.message(Command("add_channel"))
@router.message(F.text.regexp(r"^/add_channel(?:@\w+)?\s+"))
async def command_add_channel(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Используй так: <code>/add_channel https://t.me/+example</code>",
            reply_markup=admin_keyboard(),
        )
        return

    invite_url = parts[1].strip()
    if not invite_url.startswith("https://t.me/"):
        await message.answer(
            "Укажи корректную ссылку вида <code>https://t.me/+example</code>",
            reply_markup=admin_keyboard(),
        )
        return

    created = add_required_channel(invite_url)
    if not created:
        await message.answer("Этот канал уже добавлен.", reply_markup=admin_keyboard())
        return

    await message.answer("✅ Канал добавлен в обязательные.", reply_markup=admin_keyboard())
    await message.answer(channels_help_text(), reply_markup=admin_keyboard())


@router.message(Command("remove_channel"))
@router.message(F.text.regexp(r"^/remove_channel(?:@\w+)?\s+"))
async def command_remove_channel(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Используй так: <code>/remove_channel 1</code>",
            reply_markup=admin_keyboard(),
        )
        return

    removed = remove_required_channel(parts[1].strip())
    if not removed:
        await message.answer("Не удалось удалить канал. Проверь номер или ссылку.", reply_markup=admin_keyboard())
        return

    await message.answer("✅ Канал удалён.", reply_markup=admin_keyboard())
    await message.answer(channels_help_text(), reply_markup=admin_keyboard())


@router.message(Command("support"))
async def command_support(message: Message) -> None:
    name = html.escape(getattr(message.from_user, "first_name", None) or "друг")
    _pending_support_users.add(message.from_user.id)
    await message.answer(build_support_prompt(name))


@router.message(lambda message: message.from_user is not None and message.from_user.id in _pending_support_users)
async def handle_support_message(message: Message) -> None:
    if not message.text or message.text.startswith("/"):
        await message.answer("Пожалуйста, отправь сообщение обычным текстом.")
        return

    _pending_support_users.discard(message.from_user.id)
    await notify_admins_about_support(message.bot, message.from_user, message.text)
    await message.answer(build_support_success())


@router.message(Command("support_answer"))
async def command_support_answer(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    body = (message.text or "").split(maxsplit=1)
    if len(body) < 2 or "|" not in body[1]:
        await message.answer(
            "Используй так: <code>/support_answer 123456789 | Текст ответа</code>\n"
            "или <code>/support_answer @username | Текст ответа</code>"
        )
        return

    target_raw, reply_text = body[1].split("|", maxsplit=1)
    target_raw = target_raw.strip()
    reply_text = reply_text.strip()

    if not target_raw or not reply_text:
        await message.answer(
            "Используй так: <code>/support_answer 123456789 | Текст ответа</code>\n"
            "или <code>/support_answer @username | Текст ответа</code>"
        )
        return

    analytics_service, _ = require_services()
    users, unresolved = analytics_service.find_users_by_refs([target_raw])
    if not users:
        unresolved_text = ", ".join(unresolved) if unresolved else target_raw
        await message.answer(f"Не удалось найти пользователя: <code>{html.escape(unresolved_text)}</code>")
        return

    user = users[0]
    target_id = user["user_id"]

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=f"<b>Ответ поддержки</b>\n\n{html.escape(reply_text)}",
        )
        await message.answer(f"✅ Ответ отправлен пользователю <code>{target_id}</code>")
    except Exception as exc:
        await message.answer(
            f"Не удалось отправить ответ пользователю <code>{target_id}</code>\n\n"
            f"Ошибка: <code>{html.escape(str(exc))}</code>"
        )


@router.message(Command("send"))
async def command_send(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    parsed = parse_send_command(message.text or "")
    if parsed is None:
        await message.answer(mailing_help_text(), reply_markup=admin_keyboard())
        return

    targets, outgoing_text = parsed
    analytics_service, _ = require_services()

    if len(targets) == 1 and targets[0].lower() == "all":
        users = analytics_service.get_all_users()
        await send_message_to_users(message, users, outgoing_text)
        return

    users, unresolved = analytics_service.find_users_by_refs(targets)

    if not users:
        unresolved_text = ", ".join(unresolved) if unresolved else "—"
        await message.answer(
            "Не нашёл ни одного получателя в базе.\n\n"
            f"Не найдены: {html.escape(unresolved_text)}",
            reply_markup=admin_keyboard(),
        )
        return

    await send_message_to_users(message, users, outgoing_text, unresolved=unresolved)


@router.message(Command("send_segment"))
async def command_send_segment(message: Message) -> None:
    if not await ensure_admin_message(message):
        return

    parsed = parse_segment_command(message.text or "")
    if parsed is None:
        await message.answer(mailing_help_text(), reply_markup=admin_keyboard())
        return

    alias, outgoing_text = parsed
    segment = get_segment(alias)
    if segment is None:
        await message.answer("Неизвестный сегмент.\n\n" + segments_help_text(), reply_markup=admin_keyboard())
        return

    step, description = segment
    analytics_service, _ = require_services()
    users = analytics_service.get_users_by_step(step, limit=5000)
    if not users:
        await message.answer(
            f"По сегменту «{html.escape(alias)}» пользователей пока нет.",
            reply_markup=admin_keyboard(),
        )
        return

    await message.answer(
        f"Начинаю рассылку по сегменту: <b>{html.escape(description)}</b>\n"
        f"Найдено пользователей: <b>{len(users)}</b>"
    )
    await send_message_to_users(message, users, outgoing_text)


@router.message(Command("reset_nurture"))
async def command_reset_nurture(message: Message) -> None:
    if not await ensure_admin_message(message):
        return
    analytics_service, _ = require_services()

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Используй так: <code>/reset_nurture 123456789</code> или <code>/reset_nurture @username</code>")
        return

    ok = analytics_service.reset_nurture(parts[1].strip())
    if not ok:
        await message.answer("Не удалось сбросить прогрев: пользователь не найден или ещё не вошёл в воронку.")
        return

    await message.answer("✅ Прогрев для пользователя сброшен. Теперь цепочка начнётся заново от нового последнего действия.")


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


@router.callback_query(lambda c: c.data == "admin:segments")
async def callback_admin_segments(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    await callback.answer()
    await callback.message.answer(segments_help_text(), reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin:channels")
async def callback_admin_channels(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    await callback.answer()
    await callback.message.answer(channels_help_text(), reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin:send")
async def callback_admin_send(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return
    await callback.answer()
    await callback.message.answer(mailing_help_text(), reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin:notify_on")
async def callback_admin_notify_on(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return

    _notify_enabled_users.add(callback.from_user.id)
    _save_notify_users()
    await callback.answer("Уведомления включены")
    await callback.message.answer(
        "✅ Уведомления о новых входах в бота включены.",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(lambda c: c.data == "admin:notify_off")
async def callback_admin_notify_off(callback: CallbackQuery) -> None:
    if not await ensure_admin_callback(callback):
        return

    _notify_enabled_users.discard(callback.from_user.id)
    _save_notify_users()
    await callback.answer("Уведомления выключены")
    await callback.message.answer(
        "🔕 Уведомления о новых входах в бота выключены.",
        reply_markup=admin_keyboard(),
    )


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