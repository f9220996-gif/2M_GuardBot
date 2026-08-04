# -*- coding: utf-8 -*-
"""
پنل مدیریت گروه در پی‌وی ربات:
- لیست گروه‌هایی که کاربر ربات رو بهشون اضافه کرده
- برای هر گروه: روشن/خاموش کردن قابلیت‌ها، دیدن بن‌شده‌ها/سکوت‌خورده‌ها/اخطارگرفته‌ها با دلیل
"""

import time
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner


def _fmt_time(ts):
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


async def _user_can_see_group(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


# ---------------------------------------------------------------------------
# لیست گروه‌های کاربر
# ---------------------------------------------------------------------------

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
        if query:
            await query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text)
        return

    rows = []
    for g in groups:
        status = "🟢" if g["is_active"] else "🔴"
        lock = "🔒" if g["is_locked"] else "🔓"
        rows.append([InlineKeyboardButton(
            f"{status}{lock} {g['title'] or g['chat_id']}",
            callback_data=f"grp_open:{g['chat_id']}"
        )])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")])

    text = "⚙️ پنل مدیریت گروه\n\nیکی از گروه‌های زیر رو انتخاب کن:"
    markup = InlineKeyboardMarkup(rows)
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# پنل یک گروه خاص
# ---------------------------------------------------------------------------

def _group_panel_keyboard(chat_id, group):
    lock_btn = (
        InlineKeyboardButton("🔓 باز کردن گروه", callback_data=f"grp_unlock:{chat_id}")
        if group["is_locked"] else
        InlineKeyboardButton("🔒 قفل کردن گروه", callback_data=f"grp_lock:{chat_id}")
    )
    active_btn = (
        InlineKeyboardButton("⛔️ خاموش کردن ربات در این گروه", callback_data=f"grp_active_off:{chat_id}")
        if group["is_active"] else
        InlineKeyboardButton("✅ روشن کردن ربات در این گروه", callback_data=f"grp_active_on:{chat_id}")
    )
    return InlineKeyboardMarkup([
        [lock_btn],
        [active_btn],
        [InlineKeyboardButton("⛔️ لیست بن‌شده‌ها", callback_data=f"grp_banned:{chat_id}")],
        [InlineKeyboardButton("🔇 لیست سکوت‌خورده‌ها", callback_data=f"grp_muted:{chat_id}")],
        [InlineKeyboardButton("⚠️ لیست اخطارگرفته‌ها", callback_data=f"grp_warned:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت به لیست گروه‌ها", callback_data="panel_my_groups")],
    ])


async def open_group_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ این گروه مال شما نیست.", show_alert=True)
        return

    group = db.get_group(chat_id)
    if not group:
        await query.edit_message_text("این گروه پیدا نشد.")
        return

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
    await query.edit_message_text(text, reply_markup=_group_panel_keyboard(chat_id, group))


async def toggle_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    from telegram import ChatPermissions
    if action == "grp_lock":
        try:
            await context.bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
        except Exception:
            pass
        db.set_group_lock(chat_id, True, None)
        await query.answer("گروه قفل شد ✅")
    else:
        try:
            await context.bot.set_chat_permissions(
                chat_id,
                ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True,
                    can_send_other_messages=True, can_add_web_page_previews=True,
                )
            )
        except Exception:
            pass
        for job in context.job_queue.get_jobs_by_name(f"unlock_{chat_id}"):
            job.schedule_removal()
        db.set_group_lock(chat_id, False, None)
        await query.answer("گروه باز شد ✅")

    group = db.get_group(chat_id)
    text = (
        f"⚙️ پنل مدیریت گروه: {group['title']}\n\n"
        f"وضعیت ربات: {'🟢 فعال' if group['is_active'] else '🔴 خاموش'}\n"
        f"وضعیت گروه: {'🔒 قفل' if group['is_locked'] else '🔓 باز'}"
    )
    await query.edit_message_text(text, reply_markup=_group_panel_keyboard(chat_id, group))


async def toggle_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_group_active(chat_id, action == "grp_active_on")
    await query.answer("ذخیره شد ✅")

    group = db.get_group(chat_id)
    text = (
        f"⚙️ پنل مدیریت گروه: {group['title']}\n\n"
        f"وضعیت ربات: {'🟢 فعال' if group['is_active'] else '🔴 خاموش'}\n"
        f"وضعیت گروه: {'🔒 قفل' if group['is_locked'] else '🔓 باز'}"
    )
    await query.edit_message_text(text, reply_markup=_group_panel_keyboard(chat_id, group))


# ---------------------------------------------------------------------------
# لیست بن‌شده‌ها / سکوت‌خورده‌ها / اخطارگرفته‌ها
# ---------------------------------------------------------------------------

async def show_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    rows = db.get_all_banned_users(chat_id)
    if not rows:
        text = "⛔️ لیست بن‌شده‌ها\n\nهیچ کاربری بن نشده."
    else:
        lines = ["⛔️ لیست بن‌شده‌ها:\n"]
        for r in rows:
            reason = r["reason"] if r["has_reason"] and r["reason"] else "بدون دلیل ثبت‌شده"
            lines.append(f"• {r['username']} — {reason} ({_fmt_time(r['banned_at'])})")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
    await query.edit_message_text(text[:4000], reply_markup=kb)


async def show_muted_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    rows = db.get_active_mutes(chat_id)
    if not rows:
        text = "🔇 لیست سکوت‌خورده‌ها\n\nهیچ کاربری سکوت نیست."
    else:
        lines = ["🔇 لیست سکوت‌خورده‌ها:\n"]
        for r in rows:
            reason = r["reason"] if r["has_reason"] and r["reason"] else "بدون دلیل ثبت‌شده"
            until = _fmt_time(r["until_at"]) if r["until_at"] else "نامحدود"
            lines.append(f"• {r['username']} — {reason} (تا {until})")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
    await query.edit_message_text(text[:4000], reply_markup=kb)


async def show_warned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    rows = db.get_all_warned_users(chat_id)
    if not rows:
        text = "⚠️ لیست اخطارگرفته‌ها\n\nهیچ کاربری اخطار نگرفته."
    else:
        lines = ["⚠️ لیست اخطارگرفته‌ها:\n"]
        for r in rows:
            lines.append(f"• {r['username']} — {r['cnt']} اخطار (آخرین: {_fmt_time(r['last_at'])})")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
    await query.edit_message_text(text[:4000], reply_markup=kb)
