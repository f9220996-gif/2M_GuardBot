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
    CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters
)

import database as db
from config import BOT_TOKEN, CREATOR_ID

from start import cmd_start, on_help_button
from moderation import (
    cmd_khamoshi, cmd_roshan, cmd_sokoot, cmd_azad_kon, cmd_ban_kon,
    cmd_pak, cmd_gif_ban, cmd_sticker_ban, check_blacklisted_media
)
from bad_words_filter import check_message_for_bad_words
from games import (
    cmd_tas, cmd_shir_khat, cmd_sang_kaghaz_gheychi, cmd_hads_adad, cmd_hads
)
from panel import (
    show_my_groups, open_group_panel, toggle_lock, toggle_active,
    show_banned_list, show_muted_list, show_warned_list,
    show_mute_detail, release_mute_from_panel, ask_edit_mute_duration, set_mute_duration_from_panel
)
from creator import (
    open_creator_panel, toggle_global, ask_set_shutdown_text, receive_shutdown_text
)

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
}

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