from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .analytics import AnalyticsService

logger = logging.getLogger(__name__)

PAYMENT_NOTE_HTML = "‼️ <b>Оплатить можно любой банковской картой из любой страны и в любой валюте.</b>"

REMINDERS: tuple[dict[str, Any], ...] = (
    {
        "code": "r003",
        "hours": 3,
        "text": """{name}, заметили, что ты посмотрел(а) планер, но пока не забрал(а) его. Это нормально.

Такие решения не всегда принимаются сразу. Но есть один момент: <b>специальная цена закреплена за тобой только на ограниченное время</b>.

Если планер откликнулся, лучше забрать его сейчас, пока стоимость остаётся прежней. 👇""",
        "buttons": (("ЗАБРАТЬ ПЛАНЕР", "resume"),),
    },
    {
        "code": "r012",
        "hours": 12,
        "text": """Большинство людей откладывают не потому, что им не нужен инструмент.

Они ждут «идеального момента». С понедельника. Со следующего месяца. Когда будет больше времени.

Но изменения начинаются не в идеальный день, а в тот момент, когда ты принимаешь решение начать.

<b>Специальная цена всё ещё действует, но скоро вернётся к обычной.</b>

👇""",
        "buttons": (("ЗАБРАТЬ ПО ФИКС ЦЕНЕ!", "resume"),),
    },
    {
        "code": "r024",
        "hours": 24,
        "text": """Есть одна мысль, которую мы постоянно слышим от людей после покупки: «Жаль, что не начал(а) раньше.»

Не потому что планер волшебный, а потому что наконец появляется система, в которой всё становится понятнее: задачи, деньги, привычки, состояние.

<b>Цена для тебя пока ещё сохранена.</b>

Может, сегодня как раз тот день? 💛""",
        "buttons": (("БЕРУ ПЛАНЕР!", "resume"),),
    },
    {
        "code": "r032",
        "hours": 32,
        "text": """{name}, напомним про наборы.

Если ты понимаешь, что хочешь навести порядок не в одной сфере, а сразу в нескольких — они намного выгоднее.

☄️ <b>Экосистема роста</b> — все планеры всего за <b>1 290 р.</b> вместо <s>4 950 р.</s>

Это не просто скидка. Планеры усиливают друг друга: энергия влияет на привычки, привычки — на цели, цели — на результат.

<b>До окончания специальной цены осталось совсем немного.</b>

👇""",
        "buttons": (("БЕРУ НАБОР ЗА 1290 Р.", "bundle:ecosystem"),),
    },
    {
        "code": "r048",
        "hours": 48,
        "text": """Давай честно.

<b>349 р.</b> — это сумма, которую легко потратить за один вечер и даже не заметить.

Кофе. Доставка. Пара случайных покупок.

А потом снова удивляться, куда исчезли деньги.

😄 Да, это была небольшая провокация.

Но планер финансов действительно помогает увидеть полную картину расходов и наконец начать управлять деньгами, а не гадать, куда они исчезают.

<b>Пока цена ещё 349 р.</b>""",
        "buttons": (("ЗАБРАТЬ ПЛАНЕР", "product:finance"),),
    },
    {
        "code": "r060",
        "hours": 60,
        "text": """{name}, бывает такое, что заканчивается месяц, а ощущение — будто ничего важного не произошло?

Дел было много.

Усталости тоже.

А результата будто нет.

Это не вопрос мотивации. Это вопрос системы.

Планер задач показывает, что действительно двигает тебя вперёд, а что просто занимает время.

<b>Ещё 12 часов цена остаётся 249 р. Потом — 790 р.</b>

👇""",
        "buttons": (("ЗАБРАТЬ ПЛАНЕР ЗАДАЧ ЗА 249 Р.", "product:tasks"),),
    },
    {
        "code": "r072",
        "hours": 72,
        "text": """{name}, ты уже думаешь об этом несколько дней.

За это время можно было заполнить первые страницы и увидеть первые изменения.

Мы не хотим давить.

Но хотим напомнить: пока ты откладываешь, ничего не меняется.

<b>Специально для тебя цена всё ещё сохранена. Новые покупатели уже приобретают планеры по стандартной стоимости — от 790 р.</b>

Если планер тебе откликнулся — сейчас лучший момент.

👇""",
        "buttons": (("ЛАДНО, БЕРУ", "resume"),),
    },
    {
        "code": "r096",
        "hours": 96,
        "text": """💸 Небольшое напоминание про планер финансов.

Большинство людей не знают свои реальные расходы.

Они знают только ощущения.

Планер превращает ощущения в цифры. И именно тогда становится понятно, где можно сохранить деньги и почему раньше это не получалось.

<b>Пока ещё 349 р. Скоро цена изменится.</b>

👇""",
        "buttons": (("БЕРУ ПЛАНЕР ФИНАНСОВ", "product:finance"),),
    },
    {
        "code": "r120",
        "hours": 120,
        "text": """{name}, это уже предпоследнее напоминание.

Мы не любим писать «последний шанс» каждый день.

Но акционные цены действительно не остаются навсегда.

Если планировал(а) забрать — лучше сделать это сейчас.

👇""",
        "buttons": (
            ("СМОТРЕТЬ ПЛАНЕРЫ", "catalog"),
            ("СМОТРЕТЬ НАБОРЫ", "bundles"),
        ),
    },
    {
        "code": "r144",
        "hours": 144,
        "text": """Последнее сообщение, обещаем. 🙂

Если понимаешь, что планеры сейчас не нужны — всё хорошо.

Но если тебя останавливает только мысль «потом куплю» — учитывай, что потом цена уже будет другой.

Можно начать с самого простого.

<b>Планер задач — всего 249 р. вместо 790 р.</b>

Попробуй. Возможно, именно этого сейчас и не хватает.

👇""",
        "buttons": (("ПОПРОБОВАТЬ ЗА 249 Р.", "product:tasks"),),
    },
    {
        "code": "r145",
        "hours": 145,
        "text": """{name}, решение всегда остаётся за тобой.

Если тебя всё устраивает — ничего менять не нужно.

Но если внутри давно есть ощущение, что хочется больше порядка, спокойствия и движения вперёд — лучше начать сейчас, пока действует специальная цена.

👇""",
        "buttons": (("ХОЧУ ПЕРЕМЕН", "resume"),),
    },
    {
        "code": "r150",
        "hours": 150,
        "text": """На этом действительно всё. 💛

Изменения всегда начинаются с маленького решения.

Можно оставить всё как есть.

А можно сделать первый шаг уже сегодня.

Мы будем ждать тебя в любое время.

Единственное отличие — <b>в следующий раз специальные цены уже не будут действовать, и стоимость будет значительно выше.</b>

Если хотел(а) начать — сейчас самый выгодный момент.

👇""",
        "buttons": (("БЕРУ СЕЙЧАС", "resume"),),
    },
)

_worker_task: asyncio.Task | None = None
_analytics: AnalyticsService | None = None
_bot: Bot | None = None


def append_payment_note(text: str) -> str:
    if PAYMENT_NOTE_HTML in text:
        return text
    return f"{text}\n\n{PAYMENT_NOTE_HTML}"


def setup_nurture(analytics_service: AnalyticsService, bot: Bot) -> None:
    global _analytics, _bot, _worker_task
    _analytics = analytics_service
    _bot = bot

    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_nurture_worker(), name="nurture-worker")


def track_catalog_context(user: Any) -> None:
    if _analytics is not None:
        _analytics.set_nurture_context(user, context_type="catalog", context_id=None, payment_reached=False)


def track_product_context(user: Any, product_id: str) -> None:
    if _analytics is not None:
        _analytics.set_nurture_context(user, context_type="product", context_id=product_id, payment_reached=False)


def track_bundle_landing_context(user: Any) -> None:
    if _analytics is not None:
        _analytics.set_nurture_context(user, context_type="bundles", context_id=None, payment_reached=False)


def track_bundle_context(user: Any, bundle_id: str) -> None:
    if _analytics is not None:
        _analytics.set_nurture_context(user, context_type="bundle", context_id=bundle_id, payment_reached=False)


def track_payment_reached(user: Any, context_type: str, context_id: str | None = None) -> None:
    if _analytics is not None:
        _analytics.set_nurture_context(user, context_type=context_type, context_id=context_id, payment_reached=True)


def _callback_for_context(context_type: str | None, context_id: str | None) -> str:
    if context_type == "product" and context_id:
        return f"product:{context_id}:main"
    if context_type == "bundle" and context_id:
        return f"bundle:{context_id}"
    if context_type == "bundles":
        return "bundles"
    return "catalog"


def _callback_for_action(action: str, context_type: str | None, context_id: str | None) -> str:
    if action == "resume":
        return _callback_for_context(context_type, context_id)
    if action == "catalog":
        return "catalog"
    if action == "bundles":
        return "bundles"
    if action.startswith("product:"):
        return f"product:{action.split(':', 1)[1]}:main"
    if action.startswith("bundle:"):
        return f"bundle:{action.split(':', 1)[1]}"
    return "catalog"


def _build_keyboard(reminder: dict[str, Any], context_type: str | None, context_id: str | None) -> InlineKeyboardMarkup:
    rows = []
    for row in reminder["buttons"]:
        buttons = []
        for title, action in row:
            buttons.append(
                InlineKeyboardButton(
                    text=title,
                    callback_data=_callback_for_action(action, context_type, context_id),
                )
            )
        rows.append(buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _nurture_worker() -> None:
    while True:
        try:
            if _analytics is not None and _bot is not None:
                await _process_due_reminders()
        except Exception:
            logger.exception("Nurture worker failed")
        await asyncio.sleep(60)


async def _process_due_reminders() -> None:
    assert _analytics is not None and _bot is not None
    due_items = _analytics.get_due_nurture_reminders(REMINDERS)
    for item in due_items:
        reminder = item["reminder"]
        name = html.escape(item.get("first_name") or "друг")
        text = reminder["text"].format(name=name)
        text = append_payment_note(text)
        keyboard = _build_keyboard(reminder, item.get("context_type"), item.get("context_id"))

        try:
            await _bot.send_message(chat_id=item["user_id"], text=text, reply_markup=keyboard)
        except Exception:
            logger.exception("Failed to send nurture reminder %s to %s", reminder["code"], item["user_id"])
        finally:
            _analytics.mark_nurture_sent(item["user_id"], reminder["code"])
