# -*- coding: utf-8 -*-
"""
پنل ویرایش اخطارها: برای هر سطح (۱ تا ۳) می‌شه متن، گیف، استیکر یا عکس رو
از داخل پنل مدیریت گروه تغییر داد.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner

WAITING_WARN_TEXT_KEY = "waiting_warn_text"  # (chat_id, level)
WAITING_WARN_MEDIA_KEY = "waiting_warn_media"  # (chat_id, level)


async def _user_can_manage(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


async def open_warnedit_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("اخطار ۱", callback_data=f"warnedit_lvl:{chat_id}:1"),
            InlineKeyboardButton("اخطار ۲", callback_data=f"warnedit_lvl:{chat_id}:2"),
        ],
        [InlineKeyboardButton("اخطار ۳", callback_data=f"warnedit_lvl:{chat_id}:3")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])
    await query.edit_message_text("✏️ ویرایش اخطارها\n\nکدوم مرحله رو می‌خوای تغییر بدی؟", reply_markup=kb)


def _level_keyboard(chat_id, level):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ تغییر متن", callback_data=f"warnedit_text:{chat_id}:{level}"),
            InlineKeyboardButton("🖼 گیف/استیکر/عکس", callback_data=f"warnedit_media:{chat_id}:{level}"),
        ],
        [InlineKeyboardButton("↩️ بازنشانی به پیش‌فرض", callback_data=f"warnedit_reset:{chat_id}:{level}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"warnedit_panel:{chat_id}")],
    ])


async def open_level_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    row = db.get_warning_text(chat_id, level)
    text = row["text"] if row and row["text"] else "(پیش‌فرض)"
    media = "بدون رسانه"
    if row:
        if row["sticker_file_id"]:
            media = "استیکر ذخیره شده"
        elif row["gif_file_id"]:
            media = "گیف ذخیره شده"
        elif row["photo_file_id"]:
            media = "عکس ذخیره شده"

    await query.edit_message_text(
        f"✏️ اخطار سطح {level}\n\nمتن فعلی:\n{text}\n\nرسانه: {media}",
        reply_markup=_level_keyboard(chat_id, level)
    )


async def ask_warn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data[WAITING_WARN_TEXT_KEY] = (chat_id, level)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"warnedit_lvl:{chat_id}:{level}")]])
    await query.edit_message_text(f"✏️ متن جدید اخطار سطح {level} رو بفرست:", reply_markup=kb)


async def receive_warn_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    data = context.user_data.get(WAITING_WARN_TEXT_KEY)
    if not data:
        return False
    chat_id, level = data
    user = update.effective_user
    if not await _user_can_manage(context.bot, user.id, chat_id):
        return False

    context.user_data[WAITING_WARN_TEXT_KEY] = None
    new_text = update.effective_message.text
    db.set_warning_text(chat_id, level, text=new_text)
    await update.effective_message.reply_text(f"✅ متن اخطار سطح {level} ذخیره شد.")
    return True


async def ask_warn_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data[WAITING_WARN_MEDIA_KEY] = (chat_id, level)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"warnedit_lvl:{chat_id}:{level}")]])
    await query.edit_message_text(
        f"🖼 یک گیف، استیکر یا عکس برای اخطار سطح {level} بفرست:",
        reply_markup=kb
    )


async def receive_warn_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    data = context.user_data.get(WAITING_WARN_MEDIA_KEY)
    if not data:
        return False
    chat_id, level = data
    user = update.effective_user
    if not await _user_can_manage(context.bot, user.id, chat_id):
        return False

    message = update.effective_message
    if message.sticker:
        db.set_warning_text(chat_id, level, sticker_file_id=message.sticker.file_id)
    elif message.animation:
        db.set_warning_text(chat_id, level, gif_file_id=message.animation.file_id)
    elif message.photo:
        db.set_warning_text(chat_id, level, photo_file_id=message.photo[-1].file_id)
    else:
        await message.reply_text("❗️ این گیف/استیکر/عکس نبود. دوباره امتحان کن.")
        return True

    context.user_data[WAITING_WARN_MEDIA_KEY] = None
    await message.reply_text("✅ ذخیره شد.")
    return True


async def reset_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.reset_warning_text(chat_id, level)
    await query.answer("بازنشانی شد ✅")
    await open_level_panel(update, context)
