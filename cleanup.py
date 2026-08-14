# -*- coding: utf-8 -*-
"""
پاک‌سازی خودکار: هر چند روز یک‌بار، تعداد مشخصی از آخرین پیام‌های گروه پاک می‌شن
تا گروه شلوغ نشه. کاملاً از پنل مدیریت گروه قابل تنظیمه.
"""

import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner


async def _user_can_manage(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


def _cleanup_keyboard(chat_id):
    enabled, interval_days, count, _ = db.get_cleanup_settings(chat_id)
    toggle = (
        InlineKeyboardButton("❌ خاموش کردن", callback_data=f"cln_off:{chat_id}")
        if enabled else
        InlineKeyboardButton("✅ روشن کردن", callback_data=f"cln_on:{chat_id}")
    )
    return InlineKeyboardMarkup([
        [toggle],
        [
            InlineKeyboardButton("هر روز", callback_data=f"cln_days:{chat_id}:1"),
            InlineKeyboardButton("هر ۳ روز", callback_data=f"cln_days:{chat_id}:3"),
            InlineKeyboardButton("هر هفته", callback_data=f"cln_days:{chat_id}:7"),
        ],
        [
            InlineKeyboardButton("۲۰ پیام", callback_data=f"cln_count:{chat_id}:20"),
            InlineKeyboardButton("۳۰ پیام", callback_data=f"cln_count:{chat_id}:30"),
            InlineKeyboardButton("۵۰ پیام", callback_data=f"cln_count:{chat_id}:50"),
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])


def _cleanup_text(chat_id):
    enabled, interval_days, count, _ = db.get_cleanup_settings(chat_id)
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    return (
        f"🧹 پاک‌سازی خودکار گروه\n\n"
        f"وضعیت: {status}\n"
        f"بازه: هر {interval_days} روز\n"
        f"تعداد پیام هر بار: {count} تا\n\n"
        f"با دکمه‌های پایین بازه و تعدادش رو انتخاب کن."
    )


async def open_cleanup_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.edit_message_text(_cleanup_text(chat_id), reply_markup=_cleanup_keyboard(chat_id))


async def toggle_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_cleanup_settings(chat_id, enabled=(action == "cln_on"), last_ts=time.time())
    await query.answer("ذخیره شد ✅")
    await query.edit_message_text(_cleanup_text(chat_id), reply_markup=_cleanup_keyboard(chat_id))


async def set_cleanup_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, days = query.data.split(":")
    chat_id, days = int(chat_id), int(days)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_cleanup_settings(chat_id, interval_days=days)
    await query.answer("ذخیره شد ✅")
    await query.edit_message_text(_cleanup_text(chat_id), reply_markup=_cleanup_keyboard(chat_id))


async def set_cleanup_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, count = query.data.split(":")
    chat_id, count = int(chat_id), int(count)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_cleanup_settings(chat_id, count=count)
    await query.answer("ذخیره شد ✅")
    await query.edit_message_text(_cleanup_text(chat_id), reply_markup=_cleanup_keyboard(chat_id))


async def track_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هر پیام گروه، آیدیش رو ذخیره می‌کنه تا پاک‌سازی خودکار بدونه از کجا شروع کنه"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return
    db.update_last_message_id(chat.id, message.message_id)


async def run_auto_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """هر ساعت یک‌بار توسط job_queue اجرا می‌شه و گروه‌هایی که وقتشون رسیده رو پاک می‌کنه"""
    now = time.time()
    for chat_id in db.get_all_cleanup_enabled_chats():
        enabled, interval_days, count, last_ts = db.get_cleanup_settings(chat_id)
        if not enabled:
            continue
        if now - last_ts < interval_days * 86400:
            continue

        last_msg_id = db.get_last_message_id(chat_id)
        if not last_msg_id:
            db.set_cleanup_settings(chat_id, last_ts=now)
            continue

        deleted = 0
        for msg_id in range(last_msg_id - count, last_msg_id + 1):
            try:
                await context.bot.delete_message(chat_id, msg_id)
                deleted += 1
            except Exception:
                pass

        db.set_cleanup_settings(chat_id, last_ts=now)
        try:
            notice = await context.bot.send_message(chat_id, f"🧹 پاک‌سازی خودکار انجام شد ({deleted} پیام).")
            context.job_queue.run_once(
                _delete_notice_later, when=10,
                data={"chat_id": chat_id, "message_id": notice.message_id},
                name=f"delcln_{chat_id}_{notice.message_id}"
            )
        except Exception:
            pass


async def _delete_notice_later(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass
