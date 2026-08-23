# -*- coding: utf-8 -*-
"""
پنل مدیریت گروه در پی‌وی ربات
"""

import time
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner
from persian_date import tehran_from_ts, utc_from_ts


def _fmt_time(ts):
    if not ts:
        return "-"
    return tehran_from_ts(ts).strftime("%Y-%m-%d %H:%M")


async def _user_can_see_group(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


async def show_my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if query:
        await query.answer()

    if await is_creator(user.id):
        groups = db.get_all_groups()
    else:
        groups = db.get_groups_added_by(user.id)

    if not groups:
        text = "شما هنوز ربات رو به هیچ گروهی اضافه نکردید."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
        ])
        if query:
            await query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        return

    rows = []
    for g in groups:
        status = "🟢" if g["is_active"] else "🔴"
        lock = "🔒" if g["is_locked"] else "🔓"
        toggle_cb = f"grp_active_off:{g['chat_id']}" if g["is_active"] else f"grp_active_on:{g['chat_id']}"
        rows.append([
            InlineKeyboardButton(f"{status}{lock} {g['title'] or g['chat_id']}", callback_data=f"grp_open:{g['chat_id']}"),
            InlineKeyboardButton("🔁 روشن/خاموش", callback_data=toggle_cb),
        ])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")])

    text = "⚙️ پنل مدیریت گروه\n\nیکی از گروه‌های زیر رو انتخاب کن:"
    markup = InlineKeyboardMarkup(rows)
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)


def _group_panel_keyboard(chat_id, group):
    lock_btn = (
        InlineKeyboardButton("🔓 باز کردن گروه", callback_data=f"grp_unlock:{chat_id}")
        if group["is_locked"] else
        InlineKeyboardButton("🔒 قفل کردن گروه", callback_data=f"grp_lock:{chat_id}")
    )
    return InlineKeyboardMarkup([
        [
            lock_btn,
            InlineKeyboardButton("⛔️ بن‌شده‌ها", callback_data=f"grp_banned:{chat_id}"),
        ],
        [
            InlineKeyboardButton("🔇 سکوت‌خورده‌ها", callback_data=f"grp_muted:{chat_id}"),
            InlineKeyboardButton("⚠️ اخطارها", callback_data=f"grp_warned:{chat_id}"),
        ],
        [
            InlineKeyboardButton("🧩 قابلیت‌ها", callback_data=f"grp_features:{chat_id}"),
            InlineKeyboardButton("👋 خوش‌آمدگویی", callback_data=f"wc_panel:{chat_id}"),
        ],
        [
            InlineKeyboardButton("📩 گزارش‌ها", callback_data=f"grp_reports:{chat_id}"),
            InlineKeyboardButton("✏️ ویرایش اخطارها", callback_data=f"warnedit_panel:{chat_id}"),
        ],
        [
            InlineKeyboardButton("🌐 ترجمه", callback_data=f"tr_panel:{chat_id}"),
            InlineKeyboardButton("🧹 پاک‌سازی خودکار", callback_data=f"cln_panel:{chat_id}"),
        ],
        [InlineKeyboardButton("🗣 زبان عکس قیمت‌ها", callback_data=f"imglang_panel:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت به لیست گروه‌ها", callback_data="panel_my_groups")],
    ])


def _render_group_panel(group):
    lock_info = ""
    if group["is_locked"] and group["lock_until"]:
        remain = int(group["lock_until"] - time.time())
        if remain > 0:
            lock_info = f"\n⏳ باز شدن خودکار تا {remain // 60} دقیقه دیگر"

    text = (
        f"⚙️ پنل مدیریت گروه: {group['title']}\n\n"
        f"وضعیت ربات: {'🟢 فعال' if group['is_active'] else '🔴 خاموش'}\n"
        f"وضعیت گروه: {'🔒 قفل' if group['is_locked'] else '🔓 باز'}{lock_info}"
    )
    return text, _group_panel_keyboard(group["chat_id"], group)


async def send_group_panel_message(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    group = db.get_group(chat_id)
    if not group:
        await update.effective_message.reply_text("این گروه پیدا نشد.")
        return
    text, kb = _render_group_panel(group)
    await update.effective_message.reply_text(text, reply_markup=kb)


async def open_group_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ این گروه مال شما نیست.", show_alert=True)
        return

    group = db.get_group(chat_id
