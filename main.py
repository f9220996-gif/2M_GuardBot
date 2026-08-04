# -*- coding: utf-8 -*-
"""
تولید متن تاریخ/ساعت شمسی (جلالی) واقعی با استفاده از کتابخانه jdatetime.
"""

from datetime import datetime
import jdatetime


def format_persian_date_only(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405"""
    if dt is None:
        dt = datetime.now()
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    return jd.strftime("%d %B %Y")


def format_persian_time_only(dt: datetime = None) -> str:
    """مثال خروجی: 2:34 ب.ظ"""
    if dt is None:
        dt = datetime.now()
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    minute = dt.strftime("%M")
    period = "ب.ظ" if dt.hour >= 12 else "ق.ظ"
    return f"{hour12}:{minute} {period}"


def format_persian_datetime(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405، 2:34 ب.ظ"""
    if dt is None:
        dt = datetime.now()
    return f"{format_persian_date_only(dt)}، {format_persian_time_only(dt)}"


def build_restriction_message(until_dt: datetime, group_title: str = None) -> str:
    """متن رسمی سبک تلگرام برای اطلاع‌رسانی سکوت کاربر، با تاریخ شمسی"""
    when = format_persian_datetime(until_dt)
    if group_title:
        return f"مدیران گروه «{group_title}»، امکان ارسال پیام را برای شما تا {when} محدود کرده‌اند."
    return f"مدیران این گروه، امکان ارسال پیام را برای شما تا {when} محدود کرده‌اند."


def build_duration_text(seconds: int) -> str:
    """تبدیل ثانیه به متن خوانا مثل «۵ ساعت و ۳۰ دقیقه»"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h} ساعت")
    if m:
        parts.append(f"{m} دقیقه")
    if s:
        parts.append(f"{s} ثانیه")
    return " و ".join(parts) if parts else "چند لحظه"


async def cmd_tarikh(update, context):
    """دستور «تاریخ»: هرکسی تو گروه بنویسه، تاریخ و ساعت شمسی الان رو نشون می‌ده"""
    now = datetime.now()
    weekday_names = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    jd = jdatetime.datetime.fromgregorian(datetime=now)
    weekday = weekday_names[jd.weekday()]
    text = (
        f"📅 {weekday}، {format_persian_date_only(now)}\n"
        f"🕒 {format_persian_time_only(now)}"
    )
    await update.effective_message.reply_text(text)
�رات فارسی، بعد فیلتر فحش"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return

    text = (message.text or "").strip()
    for cmd_key in SORTED_COMMAND_KEYS:
        if text == cmd_key or text.startswith(cmd_key + " "):
            rest = text[len(cmd_key):].strip()
            context.args = rest.split() if rest else []
            await PERSIAN_COMMANDS[cmd_key](update, context)
            return

    # اگر دستور نبود، بررسی فحش
    await check_message_for_bad_words(update, context)


async def on_bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ربات به یک گروه جدید اضافه می‌شود، در دیتابیس ثبتش کن"""
    result: ChatMemberUpdated = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    if new_status in ("member", "administrator"):
        chat = result.chat
        adder = result.from_user
        db.upsert_group(
            chat.id, chat.title,
            added_by_user_id=adder.id if adder else None,
            added_by_username=(f"@{adder.username}" if adder and adder.username else (adder.full_name if adder else None))
        )
        try:
            await context.bot.send_message(
                chat.id,
                "✅ ربات با موفقیت اضافه شد!\n"
                "برای فعال شدن کامل قابلیت‌ها، لطفاً به من دسترسی ادمین کامل بدهید."
            )
        except Exception:
            pass


async def on_start_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from start import build_start_keyboard, START_TEXT
    query = update.callback_query
    await query.answer()
    bot_username = (await context.bot.get_me()).username
    await query.edit_message_text(
        START_TEXT,
        reply_markup=build_start_keyboard(update.effective_user.id, bot_username)
    )


def main():
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "❌ لطفاً اول BOT_TOKEN رو در config.py یا متغیر محیطی ست کنید."
        )
    if not CREATOR_ID:
        logger.warning("⚠️ CREATOR_ID تنظیم نشده — پنل ویژه سازنده کار نخواهد کرد.")

    db.init_db()

    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ---- گیت خاموشی سراسری: اگر سازنده ربات رو خاموش کرده باشه، این دو تابع
    # قبل از هر پردازشی چک می‌کنن و در گروه سکوت می‌کنن، در پی‌وی متن خاموشی میدن ----

    async def guarded_group_text(update, context):
        if not db.is_global_active() and update.effective_user.id != CREATOR_ID:
            return
        await on_group_text(update, context)

    async def guarded_private_text(update, context):
        chat = update.effective_chat
        user = update.effective_user
        if not db.is_global_active() and user.id != CREATOR_ID:
            if chat.type == "private":
                await update.effective_message.reply_text(db.get_shutdown_message())
            return
        # در پی‌وی فقط منتظر متن جدید پیام خاموشی (از پنل سازنده) می‌مانیم
        await receive_shutdown_text(update, context)

    # ---- دستورات استاندارد ----
    app.add_handler(CommandHandler("start", cmd_start))

    # ---- پیام‌های متنی پی‌وی (دستورات فارسی که در پی‌وی هم معنی ندارن ولی متن خاموشی رو می‌گیره) ----
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, guarded_private_text
    ))

    # ---- پیام‌های متنی گروه (دستورات فارسی + فیلتر فحش) ----
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, guarded_group_text
    ))

    # ---- چک لیست سیاه گیف/استیکر روی هر پیام مدیا ----
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.ANIMATION | filters.Sticker.ALL),
        check_blacklisted_media
    ))

    # ---- عضویت ربات در گروه جدید ----
    app.add_handler(ChatMemberHandler(on_bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))

    # ---- دکمه‌های شیشه‌ای (Callback Query) ----
    app.add_handler(CallbackQueryHandler(on_help_button, pattern="^help_commands$"))
    app.add_handler(CallbackQueryHandler(on_start_menu_button, pattern="^start_menu$"))
    app.add_handler(CallbackQueryHandler(show_my_groups, pattern="^panel_my_groups$"))
    app.add_handler(CallbackQueryHandler(open_group_panel, pattern=r"^grp_open:"))
    app.add_handler(CallbackQueryHandler(toggle_lock, pattern=r"^grp_(lock|unlock):"))
    app.add_handler(CallbackQueryHandler(toggle_active, pattern=r"^grp_active_(on|off):"))
    app.add_handler(CallbackQueryHandler(show_banned_list, pattern=r"^grp_banned:"))
    app.add_handler(CallbackQueryHandler(show_muted_list, pattern=r"^grp_muted:"))
    app.add_handler(CallbackQueryHandler(show_mute_detail, pattern=r"^mute_user:"))
    app.add_handler(CallbackQueryHandler(release_mute_from_panel, pattern=r"^mute_release:"))
    app.add_handler(CallbackQueryHandler(ask_edit_mute_duration, pattern=r"^mute_edit:"))
    app.add_handler(CallbackQueryHandler(set_mute_duration_from_panel, pattern=r"^mute_setdur:"))
    app.add_handler(CallbackQueryHandler(show_warned_list, pattern=r"^grp_warned:"))
    app.add_handler(CallbackQueryHandler(open_creator_panel, pattern="^creator_panel_open$"))
    app.add_handler(CallbackQueryHandler(toggle_global, pattern="^creator_global_(on|off)$"))
    app.add_handler(CallbackQueryHandler(ask_set_shutdown_text, pattern="^creator_set_msg$"))

    logger.info("🤖 ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()