from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, ChatJoinRequest, Message

# Импорты ваших модулей
from .access_guard import (
    CHECK_ACCESS_CALLBACK,
    build_access_keyboard,
    has_channel_access,
    register_join_request,
    retry_access_text,
    setup_access_guard,
    start_access_text,
)
from .admin_panel import notify_admins_about_start, router as admin_router, setup_admin_panel
from .analytics import AnalyticsService
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
    url_button,
)
from .media import MediaNotFoundError, send_album
from .nurture import (
    append_payment_note,
    setup_nurture,
    track_bundle_context,
    track_bundle_landing_context,
    track_catalog_context,
    track_payment_reached,
    track_product_context,
)
from .utils import render_text, user_first_name

# --- 1. ИНИЦИАЛИЗАЦИЯ (ОПРЕДЕЛЯЕМ РОУТЕР В НАЧАЛЕ) ---
router = Router()
logger = logging.getLogger(__name__)
analytics_service: AnalyticsService | None = None


# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ АНАЛИТИКИ ---
def track_user(user: object) -> None:
    if analytics_service and user is not None:
        analytics_service.identify_user(user)


def track_event(user: object, event_type: str, *, step: str | None = None, payload: dict | None = None) -> None:
    if analytics_service and user is not None:
        analytics_service.track_event(user, event_type=event_type, step=step, payload=payload)


def track_step(user: object, step: str, *, payload: dict | None = None) -> None:
    if analytics_service and user is not None:
        analytics_service.track_step(user, step=step, payload=payload)


async def send_missing_media_notice(target: Message | CallbackQuery) -> None:
    text = (
        "Не удалось найти изображения для этого раздела. "
        "Проверь, что файлы лежат в нужной папке внутри <b>assets</b>."
    )
    if isinstance(target, CallbackQuery):
        await target.message.answer(text)
    else:
        await target.answer(text)


# --- 3. ЛОГИКА ОТОБРАЖЕНИЯ КОНТЕНТА ---

async def send_product_album(callback: CallbackQuery, product_id: str, source: str, config: Config) -> None:
    product = PRODUCTS[product_id]
    name = user_first_name(callback.from_user)
    caption = render_text(product.album_caption, name=name)
    caption = append_payment_note(caption)
    chat_id = callback.message.chat.id
    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(bot=callback.bot, chat_id=chat_id, base_dir=config.project_dir, relative_dir=product.asset_dir,
                         caption=caption)
    except MediaNotFoundError:
        await send_missing_media_notice(callback)
        return
    await callback.message.answer("Выбери цвет своего планера 🎨",
                                  reply_markup=choose_color_keyboard(product_id, source, "product"))


async def send_bundle_album(callback: CallbackQuery, bundle_id: str, config: Config) -> None:
    bundle = BUNDLES[bundle_id]
    caption = append_payment_note(bundle.album_caption)
    chat_id = callback.message.chat.id
    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(bot=callback.bot, chat_id=chat_id, base_dir=config.project_dir,
                         relative_dir="assets/planners/combo", caption=caption, specific_files=(bundle.image_file,))
    except MediaNotFoundError:
        await send_missing_media_notice(callback)
        return
    await callback.message.answer("Выбери цвет своего планера 🎨",
                                  reply_markup=choose_color_keyboard(bundle_id, "bundle", "bundle"))


async def send_offer_album(callback: CallbackQuery, config: Config) -> None:
    name = user_first_name(callback.from_user)
    caption = render_text(CHANNEL_OFFER_CAPTION, name=name)
    caption = append_payment_note(caption)
    chat_id = callback.message.chat.id
    try:
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        await send_album(bot=callback.bot, chat_id=chat_id, base_dir=config.project_dir,
                         relative_dir="assets/channel_offer", caption=caption)
    except MediaNotFoundError:
        await send_missing_media_notice(callback)
        return
    await callback.message.answer("Выбери следующий шаг 👇", reply_markup=offer_keyboard())


# --- 4. ХЕНДЛЕРЫ ПРОВЕРКИ ДОСТУПА ---

@router.chat_join_request()
async def on_chat_join_request(join_request: ChatJoinRequest) -> None:
    """Срабатывает, когда пользователь подает заявку в канал."""
    register_join_request(join_request.chat.id, join_request.from_user.id)
    logger.info(f"User {join_request.from_user.id} requested to join channel {join_request.chat.id}")


@router.callback_query(F.data == CHECK_ACCESS_CALLBACK)
async def check_channel_access_handler(callback: CallbackQuery) -> None:
    """Кнопка 'Я ПОДАЛ ЗАЯВКУ'."""
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        # Отвечаем алертом, чтобы убрать часики на кнопке и показать ошибку
        await callback.answer("Заявка не найдена. Пожалуйста, сначала подайте заявку в канал!", show_alert=True)
        await callback.message.answer(retry_access_text(), reply_markup=build_access_keyboard())
        return

    # Если доступ есть
    await callback.answer("Доступ открыт! ✅", show_alert=True)
    track_step(callback.from_user, "catalog_menu")
    await callback.message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))


# --- 5. КОМАНДЫ БОТА ---

@router.message(Command("start"))
async def command_start(message: Message) -> None:
    track_user(message.from_user)
    if analytics_service is not None:
        analytics_service.restart_nurture_cycle(message.from_user)

    # Проверка доступа
    has_access = await has_channel_access(message.bot, message.from_user.id)
    if not has_access:
        name = user_first_name(message.from_user)
        await message.answer(start_access_text(name), reply_markup=build_access_keyboard())
    else:
        # Сразу каталог
        await message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))

    await notify_admins_about_start(message.bot, message.from_user)


@router.message(Command("menu"))
async def command_menu(message: Message) -> None:
    has_access = await has_channel_access(message.bot, message.from_user.id)
    if not has_access:
        await message.answer(start_access_text(user_first_name(message.from_user)),
                             reply_markup=build_access_keyboard())
        return
    await message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))


# --- 6. ХЕНДЛЕРЫ КАТАЛОГА (С ПРОВЕРКОЙ ДОСТУПА) ---

@router.callback_query(F.data == "catalog")
async def open_catalog(callback: CallbackQuery) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        await callback.answer("Подпишитесь на канал!", show_alert=True)
        await callback.message.answer(retry_access_text(), reply_markup=build_access_keyboard())
        return

    await callback.answer()
    await callback.message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))


@router.callback_query(F.data.startswith("product:"))
async def open_product(callback: CallbackQuery, config: Config) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        await callback.answer("Доступ ограничен ❌", show_alert=True)
        return

    await callback.answer("Загружаю...")
    _, product_id, source = callback.data.split(":", maxsplit=2)
    if product_id in PRODUCTS:
        await send_product_album(callback, product_id, source, config)


@router.callback_query(F.data.startswith("bundle:"))
async def open_bundle(callback: CallbackQuery, config: Config) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        await callback.answer("Доступ ограничен ❌", show_alert=True)
        return

    await callback.answer("Загружаю...")
    _, bundle_id = callback.data.split(":", maxsplit=1)
    if bundle_id in BUNDLES:
        await send_bundle_album(callback, bundle_id, config)


@router.callback_query(F.data == "bundles")
async def open_bundles(callback: CallbackQuery) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access: return await callback.answer("Подпишитесь!", show_alert=True)

    await callback.answer()
    await callback.message.answer(render_text(BUNDLES_LANDING_TEXT, name=user_first_name(callback.from_user)),
                                  reply_markup=bundles_keyboard())


# --- 7. ЗАПУСК И НАСТРОЙКА ---

async def on_startup(bot: Bot, config: Config) -> None:
    global analytics_service
    if analytics_service is None:
        analytics_service = AnalyticsService(config.analytics_db_path)
        analytics_service.initialize()

    setup_admin_panel(analytics_service, config)
    setup_access_guard(config)
    setup_nurture(analytics_service, bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Каталог")
    ])


async def build_dispatcher(config: Config) -> Dispatcher:
    dp = Dispatcher()
    dp["config"] = config
    dp.include_router(admin_router)
    dp.include_router(router)
    return dp


async def main() -> None:
    config = Config.load()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = await build_dispatcher(config)
    logger.info("Bot starting...")
    await on_startup(bot, config)
    # ВАЖНО: разрешаем chat_join_request
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), config=config)


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
