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
from persian_date import tehran_from_ts, utc_from_ts


def _fmt_time(ts):
    if not ts:
        return "-"
    return tehran_from_ts(ts).strftime("%Y-%m-%d %H:%M")


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


# ---------------------------------------------------------------------------
# پنل یک گروه خاص
# ---------------------------------------------------------------------------

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
        [InlineKeyboardButton("🌐 ترجمه", callback_data=f"tr_panel:{chat_id}")],
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
    await show_my_groups(update, context)


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
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
        await query.edit_message_text(text, reply_markup=kb)
        return

    text = "🔇 لیست سکوت‌خورده‌ها:\n\nروی هرکس بزنید تا آزادش کنید یا مدت سکوتش رو تغییر بدید."
    rows_kb = []
    for r in rows:
        until = _fmt_time(r["until_at"]) if r["until_at"] else "نامحدود"
        rows_kb.append([InlineKeyboardButton(
            f"{r['username']} — تا {until}",
            callback_data=f"mute_user:{chat_id}:{r['user_id']}"
        )])
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows_kb))


async def _render_mute_detail(query, chat_id, target_id):
    record = db.get_mute_record(chat_id, target_id)
    if not record:
        await query.edit_message_text(
            "این کاربر دیگه سکوت نیست.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_muted:{chat_id}")]])
        )
        return

    reason = record["reason"] if record["has_reason"] and record["reason"] else "بدون دلیل ثبت‌شده"
    until = _fmt_time(record["until_at"]) if record["until_at"] else "نامحدود"
    text = (
        f"🔇 {record['username']}\n\n"
        f"دلیل: {reason}\n"
        f"سکوت تا: {until}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔊 آزاد کردن فوری", callback_data=f"mute_release:{chat_id}:{target_id}")],
        [InlineKeyboardButton("✏️ تغییر مدت زمان", callback_data=f"mute_edit:{chat_id}:{target_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_muted:{chat_id}")],
    ])
    await query.edit_message_text(text, reply_markup=kb)


async def show_mute_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, chat_id, target_id = query.data.split(":")
    chat_id, target_id = int(chat_id), int(target_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await _render_mute_detail(query, chat_id, target_id)


async def release_mute_from_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, target_id = query.data.split(":")
    chat_id, target_id = int(chat_id), int(target_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    from telegram import ChatPermissions
    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True,
                can_send_other_messages=True, can_add_web_page_previews=True,
            )
        )
    except Exception:
        pass
    db.remove_mute(chat_id, target_id)
    await query.answer("آزاد شد ✅")

    rows = db.get_active_mutes(chat_id)
    if not rows:
        text = "🔇 لیست سکوت‌خورده‌ها\n\nهیچ کاربری سکوت نیست."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
        await query.edit_message_text(text, reply_markup=kb)
        return
    text = "🔇 لیست سکوت‌خورده‌ها:\n\nروی هرکس بزنید تا آزادش کنید یا مدت سکوتش رو تغییر بدید."
    rows_kb = []
    for r in rows:
        until = _fmt_time(r["until_at"]) if r["until_at"] else "نامحدود"
        rows_kb.append([InlineKeyboardButton(
            f"{r['username']} — تا {until}",
            callback_data=f"mute_user:{chat_id}:{r['user_id']}"
        )])
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows_kb))


DURATION_PRESETS = [
    ("5 دقیقه", 5), ("10 دقیقه", 10), ("30 دقیقه", 30),
    ("1 ساعت", 60), ("3 ساعت", 180), ("12 ساعت", 720), ("24 ساعت", 1440),
]


async def ask_edit_mute_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, chat_id, target_id = query.data.split(":")
    chat_id, target_id = int(chat_id), int(target_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    rows_kb = []
    line = []
    for label, minutes in DURATION_PRESETS:
        line.append(InlineKeyboardButton(label, callback_data=f"mute_setdur:{chat_id}:{target_id}:{minutes}"))
        if len(line) == 2:
            rows_kb.append(line)
            line = []
    if line:
        rows_kb.append(line)
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"mute_user:{chat_id}:{target_id}")])

    await query.edit_message_text(
        "⏱ مدت زمان جدید سکوت رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(rows_kb)
    )


async def set_mute_duration_from_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, target_id, minutes = query.data.split(":")
    chat_id, target_id, minutes = int(chat_id), int(target_id), int(minutes)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    from telegram import ChatPermissions
    until_ts = time.time() + minutes * 60
    until_dt_api = utc_from_ts(until_ts)

    try:
        await context.bot.restrict_chat_member(
            chat_id, target_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_dt_api,
        )
    except Exception:
        pass
    db.update_mute_duration(chat_id, target_id, until_ts)
    await query.answer("مدت زمان ذخیره شد ✅")
    await _render_mute_detail(query, chat_id, target_id)


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


# ---------------------------------------------------------------------------
# روشن/خاموش کردن قابلیت‌های گروه (فیلتر فحش، بازی‌ها، بلک‌لیست و ...)
# ---------------------------------------------------------------------------

def _build_features_keyboard(chat_id):
    """چیدمان دستی و بالانس: بلک‌لیست (به‌خاطر متن طولانی) تنها تو یه ردیف، بقیه دوتا-دوتا"""
    def btn(key):
        enabled = db.is_feature_enabled(chat_id, key)
        icon = "✅" if enabled else "❌"
        return InlineKeyboardButton(f"{icon} {db.TOGGLEABLE_FEATURES[key]}", callback_data=f"feat_toggle:{chat_id}:{key}")

    rows_kb = [
        [btn("bad_words"), btn("games")],
        [btn("blacklist")],
        [btn("photos"), btn("videos")],
        [btn("documents")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ]
    return InlineKeyboardMarkup(rows_kb)


async def show_features_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.edit_message_text(
        "🧩 روشن/خاموش قابلیت‌ها\n\nروی هرکدوم بزنید تا وضعیتش عوض بشه.\n"
        "وقتی «ارسال عکس/فیلم/فایل» رو خاموش کنید، فقط مدیران و مالک گروه می‌تونن اون نوع پیام رو بفرستن؛ "
        "بقیه اگه بفرستن، پیامشون پاک می‌شه و بهشون اطلاع داده می‌شه.",
        reply_markup=_build_features_keyboard(chat_id)
    )


async def toggle_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, feature_key = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    current = db.is_feature_enabled(chat_id, feature_key)
    new_state = not current
    db.set_feature_enabled(chat_id, feature_key, new_state)

    await query.answer("روشن شد ✅" if new_state else "خاموش شد ❌")
    await query.edit_message_text(
        "🧩 روشن/خاموش قابلیت‌ها\n\nروی هرکدوم بزنید تا وضعیتش عوض بشه.\n"
        "وقتی «ارسال عکس/فیلم/فایل» رو خاموش کنید، فقط مدیران و مالک گروه می‌تونن اون نوع پیام رو بفرستن؛ "
        "بقیه اگه بفرستن، پیامشون پاک می‌شه و بهشون اطلاع داده می‌شه.",
        reply_markup=_build_features_keyboard(chat_id)
    )
    if line:
        rows_kb.append(line)
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])

    panel_text = "🧩 روشن/خاموش قابلیت‌ها\n\nروی هرکدوم بزنید تا وضعیتش عوض بشه:"
    if warning:
        panel_text += f"\n\n{warning}\nبرای رفع: تو تنظیمات ادمین‌های گروه، دسترسی «محدود کردن اعضا» رو به ربات بده."
    await query.edit_message_text(
        panel_text,
        reply_markup=InlineKeyboardMarkup(rows_kb)
    )


# ---------------------------------------------------------------------------
# لیست گزارش‌های ثبت‌شده توسط اعضا
# ---------------------------------------------------------------------------

async def show_reports_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    rows = db.get_all_reports(chat_id)
    if not rows:
        text = "📩 گزارش‌ها\n\nهیچ گزارشی ثبت نشده."
    else:
        lines = ["📩 گزارش‌های اخیر:\n"]
        for r in rows:
            lines.append(
                f"• {r['reporter_username']} ← {r['reported_username']}\n"
                f"  متن: {r['message_snippet']}\n"
                f"  ({_fmt_time(r['created_at'])})"
            )
        text = "\n\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 پاک کردن همه گزارش‌ها", callback_data=f"reports_clear:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])
    await query.edit_message_text(text[:4000], reply_markup=kb)


async def clear_reports_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.clear_reports(chat_id)
    await query.answer("پاک شد ✅")
    await show_reports_list(update, context)
