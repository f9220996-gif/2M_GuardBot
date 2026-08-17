# -*- coding: utf-8 -*-
"""
پنل انتخاب زبان متن داخل عکس‌های قیمت (رمز ارز/دلار/طلا): فارسی، انگلیسی، عربی
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner
from crypto import LANG_NAMES


async def _user_can_manage(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


def _keyboard(chat_id):
    current = db.get_image_lang(chat_id)
    rows = []
    for code, name in LANG_NAMES.items():
        mark = "✅ " if code == current else ""
        rows.append([InlineKeyboardButton(f"{mark}{name}", callback_data=f"imglang_set:{chat_id}:{code}")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])
    return InlineKeyboardMarkup(rows)


async def open_image_lang_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    current = db.get_image_lang(chat_id)
    await query.edit_message_text(
        f"🗣 زبان متن داخل عکس‌های قیمت\n\nفعلی: {LANG_NAMES.get(current, current)}\n\nیکی رو انتخاب کن:",
        reply_markup=_keyboard(chat_id)
    )


async def set_image_lang_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, code = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_image_lang(chat_id, code)
    await query.answer("ذخیره شد ✅")
    await open_image_lang_panel(update, context)
