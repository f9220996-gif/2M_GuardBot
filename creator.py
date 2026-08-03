# -*- coding: utf-8 -*-
"""
پنل ویژه سازنده ربات:
- خاموش/روشن کردن کامل ربات (فقط سازنده می‌بینه)
- تنظیم متن دلخواه پیام خاموشی
- وقتی خاموشه: تو گروه‌ها هیچی نمیگه، فقط پی‌وی جواب "خاموش در حال تعمیرات است" میده
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from config import CREATOR_ID, DEFAULT_SHUTDOWN_MESSAGE

WAITING_FOR_SHUTDOWN_TEXT = "waiting_shutdown_text"


def _creator_keyboard():
    active = db.is_global_active()
    toggle_btn = (
        InlineKeyboardButton("⛔️ خاموش کردن کامل ربات", callback_data="creator_global_off")
        if active else
        InlineKeyboardButton("✅ روشن کردن ربات", callback_data="creator_global_on")
    )
    return InlineKeyboardMarkup([
        [toggle_btn],
        [InlineKeyboardButton("✏️ تغییر متن پیام خاموشی", callback_data="creator_set_msg")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")],
    ])


async def open_creator_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if query:
        await query.answer()

    if user.id != CREATOR_ID:
        if query:
            await query.answer("⛔️ این بخش فقط برای سازنده ربات است.", show_alert=True)
        return

    active = db.is_global_active()
    msg = db.get_shutdown_message()
    text = (
        "👑 پنل ویژه سازنده\n\n"
        f"وضعیت فعلی ربات: {'🟢 روشن' if active else '🔴 خاموش (در حال تعمیرات)'}\n\n"
        f"متن فعلی پیام خاموشی:\n«{msg}»"
    )
    if query:
        await query.edit_message_text(text, reply_markup=_creator_keyboard())
    else:
        await update.effective_message.reply_text(text, reply_markup=_creator_keyboard())


async def toggle_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    action = query.data
    db.set_global_active(action == "creator_global_on")
    await query.answer("ذخیره شد ✅")
    await open_creator_panel(update, context)


async def ask_set_shutdown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()
    context.user_data[WAITING_FOR_SHUTDOWN_TEXT] = True
    await query.edit_message_text(
        "✏️ متن جدید پیام خاموشی رو بفرست.\n"
        "(اگه چیزی ننویسی و بی‌خیال بشی، متن پیش‌فرض باقی می‌مونه)\n\n"
        f"متن پیش‌فرض: «{DEFAULT_SHUTDOWN_MESSAGE}»"
    )


async def receive_shutdown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    این تابع باید قبل از سایر هندلرهای متنی پی‌وی چک بشه.
    اگر True برگردوند یعنی پیام مصرف شد (متن خاموشی ست شد).
    """
    user = update.effective_user
    if user.id != CREATOR_ID:
        return False
    if not context.user_data.get(WAITING_FOR_SHUTDOWN_TEXT):
        return False

    context.user_data[WAITING_FOR_SHUTDOWN_TEXT] = False
    new_text = update.effective_message.text
    db.set_shutdown_message(new_text)
    await update.effective_message.reply_text(f"✅ متن پیام خاموشی ذخیره شد:\n«{new_text}»")
    return True
