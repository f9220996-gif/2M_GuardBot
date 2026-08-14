# -*- coding: utf-8 -*-
"""
فایل اصلی اجرای ربات مدیریت گروه.
اجرا: python main.py
(قبلش حتما BOT_TOKEN و CREATOR_ID رو در config.py یا متغیرهای محیطی ست کنید)
"""

import logging

from telegram import Update, ChatMemberUpdated
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters,
    ApplicationHandlerStop, TypeHandler
)

import database as db
from config import BOT_TOKEN, CREATOR_ID

from start import cmd_start, on_help_button, send_start_panel, BACK_BUTTON_TEXT, BACK_STEP_BUTTON_TEXT
from moderation import (
    cmd_khamoshi, cmd_roshan, cmd_sokoot, cmd_azad_kon, cmd_ban_kon,
    cmd_pak, cmd_gif_ban, cmd_sticker_ban, check_blacklisted_media, check_media_permissions
)
from bad_words_filter import check_message_for_bad_words
from games import (
    cmd_tas, cmd_shir_khat, cmd_sang_kaghaz_gheychi, cmd_hads_adad, cmd_hads
)
from panel import (
    show_my_groups, open_group_panel, toggle_lock, toggle_active,
    show_banned_list, show_muted_list, show_warned_list,
    show_mute_detail, release_mute_from_panel, ask_edit_mute_duration, set_mute_duration_from_panel,
    show_features_panel, toggle_feature, show_reports_list, clear_reports_cb,
    open_report_detail, handle_report_action
)
from creator import (
    open_creator_panel, toggle_global, ask_set_shutdown_text, receive_shutdown_text
)
from reports import cmd_gozaresh, send_pending_reports_job
from persian_date import cmd_tarikh
from crypto import cmd_crypto_all, cmd_crypto_single, SYMBOL_MAP, FIAT_GOLD_MAP
from welcome import (
    on_new_member_welcome, open_welcome_panel, toggle_welcome,
    preview_welcome, reset_welcome, ask_edit_welcome, receive_welcome_text,
    ask_add_welcome_media, receive_welcome_media, clear_welcome_media_cb
)
from warnings_editor import (
    open_warnedit_panel, open_level_panel, ask_warn_text, receive_warn_text,
    ask_warn_media, receive_warn_media, reset_warn
)
from translate_feature import (
    cmd_tarjome, check_dot_translate, open_translate_panel, set_translate_lang_cb
)
from cleanup import (
    open_cleanup_panel, toggle_cleanup, set_cleanup_days, set_cleanup_count,
    track_last_message, run_auto_cleanup_job
)
from nav import track_nav_state, handle_back_step

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# فارسی‌سازی نام دستورات: چون خیلی از دستورات این ربات فارسی هستند
# (مثل "خاموشی"، "روشن"، "سکوت")، به‌جای CommandHandler معمولی از
# MessageHandler با فیلتر متن + پارس دستی اول پیام استفاده می‌کنیم.
# ---------------------------------------------------------------------------

PERSIAN_COMMANDS = {
    "خاموشی": cmd_khamoshi,
    "روشن": cmd_roshan,
    "سکوت": cmd_sokoot,
    "آزاد کن": cmd_azad_kon,
    "بن کن": cmd_ban_kon,
    "پاک": cmd_pak,
    "گیف بن": cmd_gif_ban,
    "استیکر بن": cmd_sticker_ban,
    "تاس": cmd_tas,
    "شیر_یا_خط": cmd_shir_khat,
    "سنگ_کاغذ_قیچی": cmd_sang_kaghaz_gheychi,
    "حدس_عدد": cmd_hads_adad,
    "حدس": cmd_hads,
    "گزارش": cmd_gozaresh,
    "ترجمه": cmd_tarjome,
    "تاریخ": cmd_tarikh,
    "رمز ارز": cmd_crypto_all,
}

# اسم‌های تک رمزارز/دلار/طلا که با نوشتن تنها اسمشون قیمت‌شون نشون داده میشه
PRICE_LOOKUP_NAMES = set(SYMBOL_MAP.keys()) | set(FIAT_GOLD_MAP.keys())

# دستوراتی که به قابلیت «بازی‌ها» وابسته‌اند؛ اگر این قابلیت خاموش باشد اجرا نمی‌شوند
GAME_COMMANDS = {"تاس", "شیر_یا_خط", "سنگ_کاغذ_قیچی", "حدس_عدد", "حدس"}

# مرتب‌سازی بر اساس طول (نزولی) تا مثلا "بن کن" قبل از "بن" چک بشه
SORTED_COMMAND_KEYS = sorted(PERSIAN_COMMANDS.keys(), key=len, reverse=True)


async def on_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های متنی گروه: اول دستورات فارسی، بعد فیلتر فحش"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return

    text = (message.text or "").strip()
    for cmd_key in SORTED_COMMAND_KEYS:
        if text == cmd_key or text.startswith(cmd_key + " "):
            if cmd_key in GAME_COMMANDS and not db.is_feature_enabled(chat.id, "games"):
                return  # بازی‌ها برای این گروه خاموش است
            rest = text[len(cmd_key):].strip()
            context.args = rest.split() if rest else []
            await PERSIAN_COMMANDS[cmd_key](update, context)
            return

    if text in PRICE_LOOKUP_NAMES:
        if text == "دلار" and not db.is_feature_enabled(chat.id, "dollar"):
            return
        await cmd_crypto_single(update, context)
        return

    if text.startswith("."):
        consumed = await check_dot_translate(update, context)
        if consumed:
            return

    # اگر دستور نبود، بررسی فحش
    await check_message_for_bad_words(update, context)


async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    راه دوم ثبت گروه: وقتی پیام «عضو جدید» شامل خودِ ربات باشه.
    این یه پشتیبان برای on_bot_added_to_group هست، چون گاهی آپدیت
    my_chat_member به هر دلیلی (مثلا کرش هم‌زمان ربات) از دست می‌ره،
    ولی پیام سیستمی «عضو جدید» تو خودِ گروه معمولا قابل‌اعتمادتره.
    """
    message = update.effective_message
    if not message or not message.new_chat_members:
        return

    me = await context.bot.get_me()
    if me.id not in [m.id for m in message.new_chat_members]:
        return  # این یه عضو معمولیه، نه خودِ ربات

    chat = update.effective_chat
    adder = message.from_user
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


async def on_bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ربات به یک گروه جدید اضافه می‌شود، در دیتابیس ثبتش کن"""
    result: ChatMemberUpdated = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return  # پی‌وی نیست، گروه واقعی نیست؛ ثبت نکن
    if new_status in ("member", "administrator"):
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


async def global_shutdown_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    این هندلر با بالاترین اولویت (group=-1) روی همه‌ی آپدیت‌ها اجرا می‌شه.
    اگه ربات به‌صورت سراسری توسط سازنده خاموش شده باشه، جلوی پردازش
    همه‌ی هندلرهای دیگه (پیام، دکمه، عضو جدید، هرچی) رو می‌گیره —
    فقط سازنده و پی‌وی (با پیام خاموشی) استثنا هستن.
    """
    if db.is_global_active():
        return
    user = update.effective_user
    if user and user.id == CREATOR_ID:
        return
    chat = update.effective_chat
    if chat and chat.type == "private" and update.effective_message:
        try:
            await update.effective_message.reply_text(db.get_shutdown_message())
        except Exception:
            pass
    raise ApplicationHandlerStop


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
        # در پی‌وی منتظر متن خاموشی (پنل سازنده) یا متن خوش‌آمدگویی (پنل گروه) می‌مانیم
        consumed = await receive_shutdown_text(update, context)
        if consumed:
            return
        consumed = await receive_welcome_text(update, context)
        if consumed:
            return
        consumed = await receive_warn_text(update, context)
        if consumed:
            return
        text = (update.effective_message.text or "").strip()
        if text == BACK_BUTTON_TEXT:
            await send_start_panel(update, context)
            context.user_data["nav_level"] = 0
            context.user_data["nav_chat_id"] = None
        elif text == BACK_STEP_BUTTON_TEXT:
            await handle_back_step(update, context)
        elif text in PRICE_LOOKUP_NAMES:
            await cmd_crypto_single(update, context)
        elif text == "رمز ارز":
            await cmd_crypto_all(update, context)

    # ---- دستورات استاندارد ----
    # ---- گیت خاموشی سراسری: بالاترین اولویت، قبل از هر هندلر دیگه‌ای ----
    app.add_handler(TypeHandler(Update, global_shutdown_gate), group=-1)
    app.add_handler(CallbackQueryHandler(track_nav_state), group=-1)

    app.add_handler(CommandHandler("start", cmd_start))

    # ---- پیام‌های متنی پی‌وی (دستورات فارسی که در پی‌وی هم معنی ندارن ولی متن خاموشی رو می‌گیره) ----
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, guarded_private_text
    ))

    # ---- گیف/استیکر/عکس ارسالی در پی‌وی (برای خوش‌آمدگویی یا ویرایش اخطارها) ----
    async def private_media_router(update, context):
        consumed = await receive_welcome_media(update, context)
        if consumed:
            return
        await receive_warn_media(update, context)

    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.Sticker.ALL | filters.ANIMATION | filters.PHOTO),
        private_media_router
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

    # ---- چک روشن/خاموش بودن ارسال عکس/فیلم/فایل/گیف/استیکر برای اعضای عادی ----
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (
            filters.PHOTO | filters.VIDEO | filters.Document.ALL |
            filters.ANIMATION | filters.Sticker.ALL
        ),
        check_media_permissions
    ), group=1)

    # ---- عضویت ربات در گروه جدید ----
    app.add_handler(ChatMemberHandler(on_bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member_welcome), group=1)

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
    app.add_handler(CallbackQueryHandler(show_features_panel, pattern=r"^grp_features:"))
    app.add_handler(CallbackQueryHandler(toggle_feature, pattern=r"^feat_toggle:"))
    app.add_handler(CallbackQueryHandler(open_welcome_panel, pattern=r"^wc_panel:"))
    app.add_handler(CallbackQueryHandler(toggle_welcome, pattern=r"^wc_(on|off):"))
    app.add_handler(CallbackQueryHandler(ask_edit_welcome, pattern=r"^wc_edit:"))
    app.add_handler(CallbackQueryHandler(preview_welcome, pattern=r"^wc_preview:"))
    app.add_handler(CallbackQueryHandler(reset_welcome, pattern=r"^wc_reset:"))
    app.add_handler(CallbackQueryHandler(show_reports_list, pattern=r"^grp_reports:"))
    app.add_handler(CallbackQueryHandler(clear_reports_cb, pattern=r"^reports_clear:"))
    app.add_handler(CallbackQueryHandler(open_report_detail, pattern=r"^report_open:"))
    app.add_handler(CallbackQueryHandler(handle_report_action, pattern=r"^report_act:"))
    app.add_handler(CallbackQueryHandler(open_warnedit_panel, pattern=r"^warnedit_panel:"))
    app.add_handler(CallbackQueryHandler(open_level_panel, pattern=r"^warnedit_lvl:"))
    app.add_handler(CallbackQueryHandler(ask_warn_text, pattern=r"^warnedit_text:"))
    app.add_handler(CallbackQueryHandler(ask_warn_media, pattern=r"^warnedit_media:"))
    app.add_handler(CallbackQueryHandler(reset_warn, pattern=r"^warnedit_reset:"))
    app.add_handler(CallbackQueryHandler(open_translate_panel, pattern=r"^tr_panel:"))
    app.add_handler(CallbackQueryHandler(set_translate_lang_cb, pattern=r"^tr_set:"))
    app.add_handler(CallbackQueryHandler(open_cleanup_panel, pattern=r"^cln_panel:"))
    app.add_handler(CallbackQueryHandler(toggle_cleanup, pattern=r"^cln_(on|off):"))
    app.add_handler(CallbackQueryHandler(set_cleanup_days, pattern=r"^cln_days:"))
    app.add_handler(CallbackQueryHandler(set_cleanup_count, pattern=r"^cln_count:"))
    app.add_handler(CallbackQueryHandler(ask_add_welcome_media, pattern=r"^wc_media:"))
    app.add_handler(CallbackQueryHandler(clear_welcome_media_cb, pattern=r"^wc_media_clear:"))
    app.add_handler(CallbackQueryHandler(show_warned_list, pattern=r"^grp_warned:"))
    app.add_handler(CallbackQueryHandler(open_creator_panel, pattern="^creator_panel_open$"))
    app.add_handler(CallbackQueryHandler(toggle_global, pattern="^creator_global_(on|off)$"))
    app.add_handler(CallbackQueryHandler(ask_set_shutdown_text, pattern="^creator_set_msg$"))

    # ---- ارسال دوره‌ای گزارش‌های اعضا به مالک هر گروه (هر ۲ دقیقه) ----
    app.job_queue.run_repeating(send_pending_reports_job, interval=120, first=120)

    # ---- پاک‌سازی خودکار پیام‌های قدیمی (هر ساعت چک می‌کنه کدوم گروه وقتش رسیده) ----
    app.job_queue.run_repeating(run_auto_cleanup_job, interval=3600, first=300)

    # ---- ثبت آخرین آیدی پیام هر گروه (برای پاک‌سازی خودکار) ----
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, track_last_message), group=2)

    logger.info("🤖 ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
