from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, ChatJoinRequest, Message

# --- ИМПОРТЫ БЕЗ ТОЧЕК ---
from access_guard import (
    CHECK_ACCESS_CALLBACK,
    build_access_keyboard,
    has_channel_access,
    register_join_request,
    retry_access_text,
    setup_access_guard,
    start_access_text,
)
from admin_panel import notify_admins_about_start, router as admin_router, setup_admin_panel
from analytics import AnalyticsService
from catalog import (
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
from config import Config
from keyboards import (
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
from media import MediaNotFoundError, send_album
from nurture import (
    append_payment_note,
    setup_nurture,
    track_bundle_context,
    track_bundle_landing_context,
    track_catalog_context,
    track_payment_reached,
    track_product_context,
)
from utils import render_text, user_first_name

# --- ИНИЦИАЛИЗАЦИЯ РОУТЕРА ---
router = Router()
logger = logging.getLogger(__name__)
analytics_service: AnalyticsService | None = None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def track_user(user: object) -> None:
    if analytics_service and user is not None:
        analytics_service.identify_user(user)

def track_event(user: object, event_type: str, *, step: str | None = None, payload: dict | None = None) -> None:
    if analytics_service and user is not None:
        analytics_service.track_event(user, event_type=event_type, step=step, payload=payload)

async def send_missing_media_notice(target: Message | CallbackQuery) -> None:
    text = "Ошибка: изображения не найдены в папке assets."
    if isinstance(target, CallbackQuery): await target.message.answer(text)
    else: await target.answer(text)

# --- ХЕНДЛЕР ЗАЯВОК ---
@router.chat_join_request()
async def on_chat_join_request(join_request: ChatJoinRequest) -> None:
    register_join_request(join_request.chat.id, join_request.from_user.id)

# --- КОМАНДЫ ---
@router.message(Command("start"))
async def command_start(message: Message) -> None:
    track_user(message.from_user)
    has_access = await has_channel_access(message.bot, message.from_user.id)
    if not has_access:
        await message.answer(start_access_text(user_first_name(message.from_user)), reply_markup=build_access_keyboard())
    else:
        await message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))
    await notify_admins_about_start(message.bot, message.from_user)

@router.callback_query(F.data == CHECK_ACCESS_CALLBACK)
async def check_access_handler(callback: CallbackQuery) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        await callback.answer("Заявка не найдена! ❌", show_alert=True)
        await callback.message.answer(retry_access_text(), reply_markup=build_access_keyboard())
        return
    await callback.answer("Доступ открыт! ✅", show_alert=True)
    await callback.message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))

@router.callback_query(F.data == "catalog")
async def open_catalog(callback: CallbackQuery) -> None:
    has_access = await has_channel_access(callback.bot, callback.from_user.id)
    if not has_access:
        await callback.answer("Сначала подпишись! ❌", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(CATALOG_TEXT, reply_markup=planners_keyboard("main"))

# --- ЗАПУСК ---
async def on_startup(bot: Bot, config: Config) -> None:
    global analytics_service
    analytics_service = AnalyticsService(config.analytics_db_path)
    analytics_service.initialize()
    setup_admin_panel(analytics_service, config)
    setup_access_guard(config)
    setup_nurture(analytics_service, bot)
    await bot.delete_webhook(drop_pending_updates=True)

async def main() -> None:
    config = Config.load()
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(router)
    await on_startup(bot, config)
    # polling с поддержкой chat_join_request
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"], config=config)

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())