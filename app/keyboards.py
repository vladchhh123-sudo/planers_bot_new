from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .catalog import BUNDLES, COLORS, PRODUCTS


BTN_GET_PLANNER = "🤩 ЗАБРАТЬ ПЛАНЕР"
BTN_CHOOSE_COLOR = "🎨 ВЫБРАТЬ ЦВЕТ"
BTN_TAKE_PLANNER = "ЗАБИРАЮ ПЛАНЕР"
BTN_LEARN_OFFER = "🔥 УЗНАТЬ ПРЕДЛОЖЕНИЕ"
BTN_WANT_CHANNEL = "🚀 ХОЧУ В КАНАЛ"
BTN_JOIN_CHANNEL = "☄️ ВСТУПИТЬ В КАНАЛ"
BTN_TAKE_ONE_PLANNER = "ПОКА ЧТО ВОЗЬМУ ПЛАНЕР"
BTN_WANT_SET = "🌶️ ХОЧУ НАБОР!"
BTN_PICK_PLANNER = "БЕРУ ПЛАНЕР"
BTN_TAKE_SET = "☄️ ЗАБРАТЬ НАБОР"
BTN_TAKE_THIS_PLANNER = "☄️ ЗАБРАТЬ ПЛАНЕР"


def one_button(text: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])


def url_button(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


def start_keyboard() -> InlineKeyboardMarkup:
    return one_button(BTN_GET_PLANNER, "catalog")


def planners_keyboard(source: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=product.button_text, callback_data=f"product:{product.id}:{source}")]
        for product in PRODUCTS.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_color_keyboard(item_id: str, source: str, kind: str) -> InlineKeyboardMarkup:
    return one_button(BTN_CHOOSE_COLOR, f"colors:{kind}:{item_id}:{source}")


def colors_keyboard(item_id: str, source: str, kind: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for index, color in enumerate(COLORS, start=1):
        row.append(InlineKeyboardButton(text=color.label, callback_data=f"color:{kind}:{item_id}:{color.id}:{source}"))
        if index % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def planner_post_color_keyboard(product_id: str, color_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_TAKE_PLANNER, callback_data=f"pay:product:{product_id}:{color_id}")],
            [InlineKeyboardButton(text=BTN_LEARN_OFFER, callback_data="offer")],
        ]
    )


def offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_WANT_CHANNEL, callback_data="offer:channel")],
            [InlineKeyboardButton(text=BTN_TAKE_ONE_PLANNER, callback_data="offer:single")],
        ]
    )


def offer_fallback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_WANT_SET, callback_data="bundles")],
            [InlineKeyboardButton(text=BTN_PICK_PLANNER, callback_data="offer:planner_menu")],
        ]
    )


def bundles_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=bundle.button_text, callback_data=f"bundle:{bundle.id}")]
        for bundle in BUNDLES.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .catalog import BUNDLES, COLORS, PRODUCTS


BTN_GET_PLANNER = "🤩 ЗАБРАТЬ ПЛАНЕР"
BTN_CHOOSE_COLOR = "🎨 ВЫБРАТЬ ЦВЕТ"
BTN_TAKE_PLANNER = "ЗАБИРАЮ ПЛАНЕР"
BTN_LEARN_OFFER = "🔥 УЗНАТЬ ПРЕДЛОЖЕНИЕ"
BTN_WANT_CHANNEL = "🚀 ХОЧУ В КАНАЛ"
BTN_JOIN_CHANNEL = "☄️ ВСТУПИТЬ В КАНАЛ"
BTN_TAKE_ONE_PLANNER = "ПОКА ЧТО ВОЗЬМУ ПЛАНЕР"
BTN_WANT_SET = "🌶️ ХОЧУ НАБОР!"
BTN_PICK_PLANNER = "БЕРУ ПЛАНЕР"
BTN_TAKE_SET = "☄️ ЗАБРАТЬ НАБОР"
BTN_TAKE_THIS_PLANNER = "☄️ ЗАБРАТЬ ПЛАНЕР"


def one_button(text: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])


def url_button(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


def start_keyboard() -> InlineKeyboardMarkup:
    return one_button(BTN_GET_PLANNER, "catalog")


def planners_keyboard(source: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=product.button_text, callback_data=f"product:{product.id}:{source}")]
        for product in PRODUCTS.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_color_keyboard(item_id: str, source: str, kind: str) -> InlineKeyboardMarkup:
    return one_button(BTN_CHOOSE_COLOR, f"colors:{kind}:{item_id}:{source}")


def colors_keyboard(item_id: str, source: str, kind: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for index, color in enumerate(COLORS, start=1):
        row.append(InlineKeyboardButton(text=color.label, callback_data=f"color:{kind}:{item_id}:{color.id}:{source}"))
        if index % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def planner_post_color_keyboard(product_id: str, color_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_TAKE_PLANNER, callback_data=f"pay:product:{product_id}:{color_id}")],
            [InlineKeyboardButton(text=BTN_LEARN_OFFER, callback_data="offer")],
        ]
    )


def offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_WANT_CHANNEL, callback_data="offer:channel")],
            [InlineKeyboardButton(text=BTN_TAKE_ONE_PLANNER, callback_data="offer:single")],
        ]
    )


def offer_fallback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_WANT_SET, callback_data="bundles")],
            [InlineKeyboardButton(text=BTN_PICK_PLANNER, callback_data="offer:planner_menu")],
        ]
    )


def bundles_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=bundle.button_text, callback_data=f"bundle:{bundle.id}")]
        for bundle in BUNDLES.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
