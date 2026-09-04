# -*- coding: utf-8 -*-
"""
پنل مدیریت گروه در پی‌وی ربات
"""

import time
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, can_access_dm_panel, is_telegram_group_creator
from persian_date import tehran_from_ts, utc_from_ts


def _fmt_time(ts):
    if not ts:
        return "-"
    return tehran_from_ts(ts).strftime("%Y-%m-%d %H:%M")


async def _user_can_see_group(bot, user_id, chat_id):
    return await can_access_dm_panel(bot, chat_id, user_id)


async def show_my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if query:
        await query.answer()

    if await is_creator(user.id):
        groups = db.get_all_groups()
    else:
        # لیست فقط شامل گروه‌هایی می‌شه که این کاربر واقعاً مالک تلگرامیِ
        # خودِ گروهه (نه هرکسی که ربات رو اضافه کرده)
        groups = []
        for g in db.get_all_groups():
            if await is_telegram_group_creator(context.bot, g["chat_id"], user.id):
                groups.append(g)

    if not groups:
        text = "شما مالک هیچ گروهی که ربات توشه نیستید."
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
        [
            InlineKeyboardButton("🗣 زبان عکس قیمت‌ها", callback_data=f"imglang_panel:{chat_id}"),
            InlineKeyboardButton("🚫 کلمات غیرمجاز", callback_data=f"badwords_panel:{chat_id}"),
        ],
        [InlineKeyboardButton("🧠 فعال‌ساز هوش مصنوعی", callback_data=f"ai_trigger_panel:{chat_id}")],
        [InlineKeyboardButton("🔤 میان‌برهای دستورات", callback_data=f"cmdshortcuts_panel:{chat_id}")],
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

    group = db.get_group(chat_id)
    if not group:
        await query.edit_message_text("این گروه پیدا نشد.")
        return

    text, kb = _render_group_panel(group)
    await query.edit_message_text(text, reply_markup=kb)


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
        await query.answer("گروه قفل شد ✔")
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
        await query.answer("گروه باز شد ✔")

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
    await query.answer("ذخیره شد ✔")
    await show_my_groups(update, context)


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
    await query.answer("آزاد شد ✔")

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
    await query.answer("مدت زمان ذخیره شد ✔")
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


def _build_features_keyboard(chat_id):
    def btn(key):
        enabled = db.is_feature_enabled(chat_id, key)
        icon = "✔" if enabled else "✘"
        return InlineKeyboardButton(f"{icon} {db.TOGGLEABLE_FEATURES[key]}", callback_data=f"feat_toggle:{chat_id}:{key}")

    rows_kb = [
        [btn("bad_words"), btn("games")],
        [btn("gifs"), btn("stickers")],
        [btn("photos"), btn("videos")],
        [btn("documents"), btn("date")],
        [btn("dollar"), btn("translate")],
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
        "🧩 روشن/خاموش قابلیت‌ها\n\nروی هرکدوم بزن تا عوض بشه.",
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

    await query.answer("روشن شد ✔" if new_state else "خاموش شد ✘")
    await query.edit_message_text(
        "🧩 روشن/خاموش قابلیت‌ها\n\nروی هرکدوم بزن تا عوض بشه.",
        reply_markup=_build_features_keyboard(chat_id)
    )


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
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")]])
        await query.edit_message_text(text, reply_markup=kb)
        return

    rows_kb = []
    for r in rows:
        rows_kb.append([InlineKeyboardButton(
            f"👤 {r['reported_username']} ({_fmt_time(r['created_at'])})",
            callback_data=f"report_open:{r['id']}"
        )])
    rows_kb.append([InlineKeyboardButton("🗑 پاک کردن همه گزارش‌ها", callback_data=f"reports_clear:{chat_id}")])
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])

    await query.edit_message_text(
        "📩 گزارش‌های اخیر\n\nروی هرکدوم بزن برای جزئیات و اقدام:",
        reply_markup=InlineKeyboardMarkup(rows_kb)
    )


async def open_report_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split(":")[1])

    report = db.get_report_by_id(report_id)
    if not report:
        await query.edit_message_text("این گزارش دیگه پیدا نشد.")
        return

    chat_id = report["chat_id"]
    user = update.effective_user
    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    text = (
        f"📩 جزئیات گزارش\n\n"
        f"گزارش‌دهنده: {report['reporter_username']}\n"
        f"گزارش‌شده: {report['reported_username']}\n"
        f"متن: {report['message_snippet']}\n"
        f"زمان: {_fmt_time(report['created_at'])}"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔇 سکوت", callback_data=f"report_act:{report_id}:mute"),
            InlineKeyboardButton("⛔️ بن", callback_data=f"report_act:{report_id}:ban"),
            InlineKeyboardButton("⚠️ اخطار", callback_data=f"report_act:{report_id}:warn"),
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_reports:{chat_id}")],
    ])
    await query.edit_message_text(text, reply_markup=kb)


async def handle_report_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, report_id, action = query.data.split(":")
    report_id = int(report_id)

    report = db.get_report_by_id(report_id)
    if not report:
        await query.answer("این گزارش دیگه پیدا نشد.", show_alert=True)
        return

    chat_id = report["chat_id"]
    target_id = report["reported_user_id"]
    target_name = report["reported_username"]
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    from telegram import ChatPermissions
    import time as _time

    if action == "mute":
        until_ts = _time.time() + 10 * 60
        from persian_date import utc_from_ts
        try:
            await context.bot.restrict_chat_member(
                chat_id, target_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=utc_from_ts(until_ts),
            )
        except Exception:
            pass
        db.add_mute(chat_id, target_id, target_name, "اقدام بر اساس گزارش عضو", True, until_ts)
        await query.answer("سکوت ۱۰ دقیقه‌ای اعمال شد ✔")

    elif action == "ban":
        try:
            await context.bot.ban_chat_member(chat_id, target_id)
        except Exception:
            pass
        db.add_ban(chat_id, target_id, target_name, "اقدام بر اساس گزارش عضو", True)
        await query.answer("بن شد ✔")

    elif action == "warn":
        level = db.get_active_warning_count(chat_id, target_id) + 1
        db.add_warning(chat_id, target_id, target_name, "اقدام بر اساس گزارش عضو", level)
        await query.answer(f"اخطار سطح {level} ثبت شد ✔")

    await open_report_detail(update, context)


async def clear_reports_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.clear_reports(chat_id)
    await query.answer("پاک شد ✔")
    await show_reports_list(update, context)


# ---------------------------------------------------------------------------
# مدیریت کلمات غیرمجاز (نمایش لیست / افزودن / حذف)
# ---------------------------------------------------------------------------

def _get_chat_specific_bad_words(chat_id):
    """فقط کلماتی که مخصوص همین گروهن (نه کلمات پیش‌فرض سراسری که بین همه گروه‌ها مشترکن)"""
    with db.get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT word FROM bad_words WHERE chat_id=?", (chat_id,))
        return [r["word"] for r in c.fetchall()]


def _bad_words_text(chat_id):
    words = _get_chat_specific_bad_words(chat_id)
    lines = ["🚫 کلمات غیرمجاز این گروه\n"]
    if not words:
        lines.append("هنوز کلمه‌ای اختصاصی برای این گروه اضافه نشده.\n(کلمات پیش‌فرض مشترک بین همه گروه‌ها همچنان فعالن.)")
    else:
        lines.append("روی هرکدوم بزن تا حذفش کنی:")
    return "\n".join(lines)


def _bad_words_keyboard(chat_id):
    words = _get_chat_specific_bad_words(chat_id)
    rows_kb = []
    for idx, word in enumerate(words):
        rows_kb.append([InlineKeyboardButton(f"🗑 {word}", callback_data=f"badwords_del:{chat_id}:{idx}")])
    rows_kb.append([InlineKeyboardButton("➕ افزودن کلمه جدید", callback_data=f"badwords_add:{chat_id}")])
    rows_kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])
    return InlineKeyboardMarkup(rows_kb)


async def _render_bad_words_panel(update_or_query, context, chat_id, via_query=True):
    text = _bad_words_text(chat_id)
    kb = _bad_words_keyboard(chat_id)
    if via_query:
        await update_or_query.edit_message_text(text, reply_markup=kb)
    else:
        await update_or_query.effective_message.reply_text(text, reply_markup=kb)


async def open_bad_words_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await _render_bad_words_panel(query, context, chat_id, via_query=True)


async def ask_add_bad_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    context.user_data["waiting_for_bad_word_chat_id"] = chat_id
    # آیدی همین پیام (تو پی‌وی ادمین) رو ذخیره می‌کنیم تا بعداً به‌جای فرستادن
    # پیام جدید، دقیقاً همینو ویرایش کنیم و دوباره تبدیلش کنیم به لیست کلمات
    context.user_data["bad_word_prompt_chat_id"] = query.message.chat_id
    context.user_data["bad_word_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"badwords_panel:{chat_id}")]
    ])
    await query.edit_message_text(
        "➕ افزودن کلمه غیرمجاز\n\n"
        "لطفاً کلمه‌ای که می‌خوای فیلتر بشه رو تایپ و ارسال کن.\n"
        "برای لغو، دستور /cancel رو بفرست.",
        reply_markup=kb
    )


async def receive_bad_word_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن کلمه‌ی جدید (باید تو guarded_private_text چک بشه)"""
    chat_id = context.user_data.get("waiting_for_bad_word_chat_id")
    if not chat_id:
        return False

    user = update.effective_user
    if not await _user_can_see_group(context.bot, user.id, chat_id):
        return False

    prompt_chat_id = context.user_data.get("bad_word_prompt_chat_id")
    prompt_message_id = context.user_data.get("bad_word_prompt_message_id")

    text = (update.effective_message.text or "").strip()

    async def _finish(feedback_line):
        context.user_data.pop("waiting_for_bad_word_chat_id", None)
        context.user_data.pop("bad_word_prompt_chat_id", None)
        context.user_data.pop("bad_word_prompt_message_id", None)

        panel_text = f"{feedback_line}\n\n{_bad_words_text(chat_id)}"
        panel_kb = _bad_words_keyboard(chat_id)

        # پاک کردن پیامی که کاربر تایپ کرد، تا فقط یه پیام (پنل) بمونه
        try:
            await update.effective_message.delete()
        except Exception:
            pass

        if prompt_chat_id and prompt_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=prompt_chat_id, message_id=prompt_message_id,
                    text=panel_text, reply_markup=panel_kb
                )
                return
            except Exception:
                pass
        # اگه ویرایش ممکن نبود (مثلاً پیام خیلی قدیمی شده)، به‌عنوان جایگزین یه پیام جدید بفرست
        await update.effective_message.reply_text(panel_text, reply_markup=panel_kb)

    if text == "/cancel":
        await _finish("❌ لغو شد.")
        return True

    if not text:
        # کلمه‌ی خالی: فقط دوباره همون پیام "لطفاً کلمه بفرست" رو نگه می‌داریم
        try:
            await update.effective_message.delete()
        except Exception:
            pass
        return True

    db.add_bad_word(chat_id, text)
    await _finish(f"✔ کلمه‌ی «{text}» اضافه شد.")
    return True


async def delete_bad_word_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, idx = query.data.split(":")
    chat_id, idx = int(chat_id), int(idx)
    user = update.effective_user

    if not await _user_can_see_group(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    words = _get_chat_specific_bad_words(chat_id)
    if 0 <= idx < len(words):
        word = words[idx]
        # حذف امن: فقط ردیف مخصوص همین گروه پاک می‌شه، نه کلمات پیش‌فرض سراسری
        with db.get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM bad_words WHERE word=? AND chat_id=?", (word, chat_id))
        await query.answer("✔ حذف شد")
    else:
        await query.answer("این کلمه دیگه پیدا نشد.")

    await _render_bad_words_panel(query, context, chat_id, via_query=True)
