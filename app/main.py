@router.message(Command("start"))
async def command_start(message: Message) -> None:
    # 1. Сначала идентифицируем пользователя для аналитики
    track_user(message.from_user)
    if analytics_service is not None:
        analytics_service.restart_nurture_cycle(message.from_user)

    track_event(message.from_user, "start_command", step="start_screen")

    # 2. ЖЕСТКАЯ ПРОВЕРКА ДОСТУПА
    # Даже если пользователь старый, мы проверяем, подана ли заявка или есть ли он в канале
    has_access = await has_channel_access(message.bot, message.from_user.id)

    if not has_access:
        # Если доступа нет (не подал заявку или не подписан)
        name = user_first_name(message.from_user)
        text = start_access_text(name)  # Текст: "Подпишись, чтобы получить планер"
        await message.answer(text, reply_markup=build_access_keyboard())

        # Уведомляем админов, что кто-то зашел, но еще не подписан
        await notify_admins_about_start(message.bot, message.from_user)
        return  # ПРЕРЫВАЕМ выполнение, дальше код не идет

    # 3. ЕСЛИ ДОСТУП ЕСТЬ (пользователь прошел проверку)
    # Показываем основной контент (каталог)
    await message.answer(
        f"С возвращением, {user_first_name(message.from_user)}! Рады тебя видеть снова.\n\n" + CATALOG_TEXT,
        reply_markup=planners_keyboard("main")
    )
    await notify_admins_about_start(message.bot, message.from_user)