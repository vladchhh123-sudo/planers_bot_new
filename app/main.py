from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, Message

from .catalog import (
    BUNDLES,
    BUNDLES_LANDING_TEXT,
    CATALOG_TEXT,
    CHANNEL_OFFER_CAPTION,
    CHANNEL_URL,
    HABITS_WHITE_SPECIAL_TEXT,
    MAIN_FLOW_AFTER_COLOR_TEXT,
    OFFER_FALLBACK_MENU_TEXT,
    OFFER_FALLBACK_TEXT,
    PAYMENT_TEXT_BUNDLE,
    PAYMENT_TEXT_CHANNEL,
    PAYMENT_TEXT_SINGLE,
    PLANNERS_LIST_BLOCK,
    PRODUCTS,
    START_TEXT,
)
from .config import Config
from .keyboards import (
    BTN_JOIN_CHANNEL,
    BTN_TAKE_SET,
    BTN_TAKE_THIS_PLANNER,
    bundles_keyboard,
    choose_color_keyboard,
    colors_keyboard,
    offer_fallback_keyboard,
    offer_keyboard,
    planner_post_color_keyboard,
    planners_keyboard,
    start_keyboard,
    url_button,
)
from .media import MediaNotFoundError, send_album
from .utils import render_text, user_first_name

router = Router()
logger = logging.getLogger(__name__)


async def send_missing_media_notice(target: Message | CallbackQuery) -> None:
    text = (
        "Не удалось найти изображения для этого раздела. "
        "Проверь, что файлы лежат в нужной папке внутри <b>assets</b>."
    )
    if isinstance(target, CallbackQuery):
        await target.message.answer(text)
    else:
        await target.answer(text)


async def send_product_album(callback: CallbackQuery, product_id: str, source: str, config: Config) -> None:
    product = PRODUCTS[product_id]
    name = user_first_name(callback.from_user)
    caption = render_text(product.album_caption, name=name)
    chat_id = callback.message.chat.id

    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(
            bot=callback.bot,
            chat_id=chat_id,
            base_dir=config.project_dir,
            relative_dir=product.asset_dir,
            caption=caption,
        )
    except MediaNotFoundError:
        logger.exception("Media not found for product %s", product_id)
        await send_missing_media_notice(callback)
        return

    await callback.message.answer(
        "Выбери цвет своего планера 🎨",
        reply_markup=choose_color_keyboard(product_id, source, "product"),
    )


async def send_bundle_album(callback: CallbackQuery, bundle_id: str, config: Config) -> None:
    bundle = BUNDLES[bundle_id]
    chat_id = callback.message.chat.id
    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(
            bot=callback.bot,
            chat_id=chat_id,
            base_dir=config.project_dir,
            relative_dir="assets/planners/combo",
            caption=bundle.album_caption,
            specific_files=(bundle.image_file,),
        )
    except MediaNotFoundError:
        logger.exception("Media not found for bundle %s", bundle_id)
        await send_missing_media_notice(callback)
        return

    await callback.message.answer(
        "Выбери цвет своего планера 🎨",
        reply_markup=choose_color_keyboard(bundle_id, "bundle", "bundle"),
    )


async def send_offer_album(callback: CallbackQuery, config: Config) -> None:
    name = user_first_name(callback.from_user)
    caption = render_text(CHANNEL_OFFER_CAPTION, name=name)
    chat_id = callback.message.chat.id

    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(
            bot=callback.bot,
            chat_id=chat_id,
            base_dir=config.project_dir,
            relative_dir="assets/channel_offer",
            caption=caption,
        )
    except MediaNotFoundError:
        logger.exception("Media not found for channel offer")
        await send_missing_media_notice(callback)
        return

    await callback.message.answer("Выбери следующий шаг 👇", reply_markup=offer_keyboard())


async def send_product_payment(callback: CallbackQuery, product_id: str, color_id: str) -> None:
    product = PRODUCTS[product_id]
    url = product.payment_urls[color_id]
    name = user_first_name(callback.from_user)
    text = render_text(PAYMENT_TEXT_SINGLE, name=name, url=url)
    await callback.message.answer(text, reply_markup=url_button(BTN_TAKE_THIS_PLANNER, url))


async def send_bundle_payment(callback: CallbackQuery, bundle_id: str, color_id: str) -> None:
    bundle = BUNDLES[bundle_id]
    url = bundle.payment_urls[color_id]
    name = user_first_name(callback.from_user)
    text = render_text(PAYMENT_TEXT_BUNDLE, name=name, url=url)
    await callback.message.answer(text, reply_markup=url_button(BTN_TAKE_SET, url))


@router.message(Command("start"))
async def command_start(message: Message) -> None:
    name = user_first_name(message.from_user)
    text = render_text(START_TEXT, name=name)
    await message.answer(text, reply_markup=start_keyboard())


@router.message(Command("menu"))
async def command_menu(message: Message) -> None:
    await message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))


@router.callback_query(F.data == "catalog")
async def open_catalog(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))


@router.callback_query(F.data == "offer")
async def open_offer(callback: CallbackQuery, config: Config) -> None:
    await callback.answer("Открываю предложение…")
    await send_offer_album(callback, config)


@router.callback_query(F.data == "offer:channel")
async def open_channel_payment(callback: CallbackQuery) -> None:
    await callback.answer()
    name = user_first_name(callback.from_user)
    text = render_text(PAYMENT_TEXT_CHANNEL, name=name, url=CHANNEL_URL)
    await callback.message.answer(text, reply_markup=url_button(BTN_JOIN_CHANNEL, CHANNEL_URL))


@router.callback_query(F.data == "offer:single")
async def open_offer_fallback(callback: CallbackQuery) -> None:
    await callback.answer()
    name = user_first_name(callback.from_user)
    text = render_text(OFFER_FALLBACK_TEXT, name=name, planners=PLANNERS_LIST_BLOCK)
    await callback.message.answer(text, reply_markup=offer_fallback_keyboard())


@router.callback_query(F.data == "offer:planner_menu")
async def open_offer_fallback_planner_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    name = user_first_name(callback.from_user)
    text = render_text(OFFER_FALLBACK_MENU_TEXT, name=name, planners=PLANNERS_LIST_BLOCK)
    await callback.message.answer(text, reply_markup=planners_keyboard("return"))


@router.callback_query(F.data == "bundles")
async def open_bundles(callback: CallbackQuery) -> None:
    await callback.answer()
    name = user_first_name(callback.from_user)
    text = render_text(BUNDLES_LANDING_TEXT, name=name)
    await callback.message.answer(text, reply_markup=bundles_keyboard())


@router.callback_query(F.data.startswith("product:"))
async def open_product(callback: CallbackQuery, config: Config) -> None:
    await callback.answer("Загружаю планер…")
    _, product_id, source = callback.data.split(":", maxsplit=2)
    if product_id not in PRODUCTS:
        return
    await send_product_album(callback, product_id, source, config)


@router.callback_query(F.data.startswith("bundle:"))
async def open_bundle(callback: CallbackQuery, config: Config) -> None:
    await callback.answer("Загружаю набор…")
    _, bundle_id = callback.data.split(":", maxsplit=1)
    if bundle_id not in BUNDLES:
        return
    await send_bundle_album(callback, bundle_id, config)


@router.callback_query(F.data.startswith("colors:"))
async def open_colors(callback: CallbackQuery) -> None:
    await callback.answer()
    _, kind, item_id, source = callback.data.split(":", maxsplit=3)
    await callback.message.answer(
        "Выбери цвет своего планера 🎨",
        reply_markup=colors_keyboard(item_id, source, kind),
    )


@router.callback_query(F.data.startswith("color:"))
async def choose_color(callback: CallbackQuery) -> None:
    await callback.answer()
    _, kind, item_id, color_id, source = callback.data.split(":", maxsplit=4)

    if kind == "product":
        if source == "return":
            await send_product_payment(callback, item_id, color_id)
            return

        text = (
            HABITS_WHITE_SPECIAL_TEXT
            if item_id == "habits" and color_id == "white"
            else MAIN_FLOW_AFTER_COLOR_TEXT
        )
        await callback.message.answer(text, reply_markup=planner_post_color_keyboard(item_id, color_id))
        return

    if kind == "bundle":
        await send_bundle_payment(callback, item_id, color_id)


@router.callback_query(F.data.startswith("pay:product:"))
async def pay_product(callback: CallbackQuery) -> None:
    await callback.answer()
    _, _, product_id, color_id = callback.data.split(":", maxsplit=3)
    await send_product_payment(callback, product_id, color_id)


async def on_startup(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Открыть каталог планеров"),
    ]
    await bot.set_my_commands(commands)


async def build_dispatcher(config: Config) -> Dispatcher:
    dp = Dispatcher()
    dp["config"] = config
    dp.include_router(router)
    return dp


async def main() -> None:
    with suppress(ImportError):
        import uvloop

        uvloop.install()

    config = Config.load()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = await build_dispatcher(config)

    logger.info("Bot is starting")
    await on_startup(bot)
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        config=config,
    )


if __name__ == "__main__":
    asyncio.run(main())
