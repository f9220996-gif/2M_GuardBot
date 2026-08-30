# -*- coding: utf-8 -*-
"""
پاک‌سازی خودکار: هر چند روز یک‌بار، تعداد مشخصی از آخرین پیام‌های گروه پاک می‌شن
تا گروه شلوغ نشه. کاملاً از پنل مدیریت گروه قابل تنظیمه.

نکته‌ی مهم درباره‌ی واحدها:
تو دیتابیس (database.py)، بازه به «ثانیه» ذخیره می‌شه (interval_seconds).
تو این فایل، برای نمایش و تنظیم راحت‌تر، همیشه با «روز» کار می‌کنیم و فقط
موقع خوندن/نوشتن از/به دیتابیس، تبدیل ثانیه↔روز انجام می‌شه.

نکته‌ی مهم درباره‌ی دکمه‌های ➖/➕:
با هر بار زدن ➖/➕ فقط یه مقدار «پیش‌نویس» (draft) تو حافظه‌ی موقت کاربر
(context.user_data) عوض می‌شه، نه دیتابیس. مقدار واقعی فقط با زدن دکمه‌ی
«✅ ذخیره» تو دیتابیس نوشته می‌شه. با «❌ لغو» هیچ تغییری اعمال نمی‌شه.
"""

import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, can_access_dm_panel

SECONDS_PER_DAY = 86400


def _get_cleanup_cursor(chat_id):
    """آیدی پیامی که پاک‌سازی باید ازش شروع کنه (پیش‌فرض: از اولین پیام‌های گروه)"""
    val = db.get_setting(f"cleanup_cursor_{chat_id}")
    return int(val) if val else 1


def _set_cleanup_cursor(chat_id, value):
    db.set_setting(f"cleanup_cursor_{chat_id}", str(value))


async def _sweep_oldest_messages(bot, chat_id, count):
    """
    از نشانگر فعلی (قدیمی‌ترین نقطه‌ای که تا الان پاک‌سازی بهش رسیده) شروع
    می‌کنه و `count` پیام رو به سمت جلو (به سمت پیام‌های جدیدتر) پاک می‌کنه،
    بعد نشانگر رو جلو می‌بره. این یعنی پاک‌سازی همیشه از قدیمی‌ترین پیام‌های
    باقی‌مونده شروع می‌شه، نه از نزدیک آخرین پیام‌ها.
    """
    cursor = _get_cleanup_cursor(chat_id)
    last_msg_id = db.get_last_message_id(chat_id)

    end = cursor + count - 1
    if last_msg_id:
        end = min(end, last_msg_id)

    deleted = 0
    if end >= cursor:
        for msg_id in range(cursor, end + 1):
            try:
                await bot.delete_message(chat_id, msg_id)
                deleted += 1
            except Exception:
                pass
        _set_cleanup_cursor(chat_id, end + 1)

    return deleted


async def _user_can_manage(bot, user_id, chat_id):
    return await can_access_dm_panel(bot, chat_id, user_id)


def _get_settings_in_days(chat_id):
    """مثل db.get_cleanup_settings ولی بازه رو به روز برمی‌گردونه، نه ثانیه"""
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    interval_days = max(1, round(interval_seconds / SECONDS_PER_DAY))
    return enabled, interval_days, count, last_ts


# ---------------------------------------------------------------------------
# پنل اصلی
# ---------------------------------------------------------------------------

def _panel_text(chat_id):
    enabled, interval_days, count, _ = _get_settings_in_days(chat_id)
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    return (
        "🧹 پاک‌سازی خودکار گروه\n\n"
        f"وضعیت: {status}\n"
        f"بازه: هر {interval_days} روز\n"
        f"تعداد پیام هر بار: {count} تا\n\n"
        "با دکمه‌های پایین تنظیم کن."
    )


def _panel_keyboard(chat_id):
    enabled, interval_days, count, _ = _get_settings_in_days(chat_id)
    toggle = (
        InlineKeyboardButton("❌ خاموش کردن", callback_data=f"cln_toggle:{chat_id}:off")
        if enabled else
        InlineKeyboardButton("✅ روشن کردن", callback_data=f"cln_toggle:{chat_id}:on")
    )
    return InlineKeyboardMarkup([
        [toggle],
        [InlineKeyboardButton(f"⏱ تنظیم بازه (فعلی: هر {interval_days} روز)", callback_data=f"cln_interval:{chat_id}")],
        [InlineKeyboardButton(f"🔢 تنظیم تعداد (فعلی: {count})", callback_data=f"cln_count_adjust:{chat_id}:open")],
        [InlineKeyboardButton("🧹 پاک‌سازی همین الان", callback_data=f"cln_run:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])


async def _render_panel(query, chat_id):
    await query.edit_message_text(_panel_text(chat_id), reply_markup=_panel_keyboard(chat_id))


async def open_cleanup_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await _render_panel(query, chat_id)


async def toggle_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, action = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_cleanup_settings(chat_id, enabled=(action == "on"), last_ts=time.time())
    await query.answer("✔ ذخیره شد")
    await _render_panel(query, chat_id)


async def run_cleanup_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاک‌سازی فوری، بدون نیاز به صبر کردن تا نوبت خودکارش برسه"""
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.answer("🧹 در حال پاک‌سازی...")

    _, _, count, _ = db.get_cleanup_settings(chat_id)
    deleted = await _sweep_oldest_messages(context.bot, chat_id, count)

    db.set_cleanup_settings(chat_id, last_ts=time.time())
    await _render_panel(query, chat_id)
    try:
        notice = await context.bot.send_message(chat_id, f"🧹 پاک‌سازی دستی انجام شد ({deleted} پیام).")
        context.job_queue.run_once(
            _delete_notice_later, when=10,
            data={"chat_id": chat_id, "message_id": notice.message_id},
            name=f"delcln_{chat_id}_{notice.message_id}"
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# تنظیم بازه (روز) با ➖ / ➕ / ذخیره / لغو
# ---------------------------------------------------------------------------

def _interval_draft_text(draft_days):
    return (
        "⏱ تنظیم بازه‌ی پاک‌سازی\n\n"
        f"مقدار در حال تنظیم: هر {draft_days} روز\n"
        "(هنوز ذخیره نشده)\n\n"
        "با ➖/➕ عدد رو تغییر بده، بعد «✅ ذخیره» رو بزن."
    )


def _interval_draft_keyboard(chat_id, draft_days):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"cln_adjust:{chat_id}:dec"),
            InlineKeyboardButton(f"{draft_days} روز", callback_data=f"cln_adjust:{chat_id}:noop"),
            InlineKeyboardButton("➕", callback_data=f"cln_adjust:{chat_id}:inc"),
        ],
        [
            InlineKeyboardButton("✅ ذخیره", callback_data=f"cln_adjust:{chat_id}:save"),
            InlineKeyboardButton("❌ لغو", callback_data=f"cln_adjust:{chat_id}:cancel"),
        ],
    ])


async def ask_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """باز کردن صفحه‌ی تنظیم بازه (شروع یه ویرایش تازه، مقدار فعلی به‌عنوان پیش‌نویس)"""
    query = update.callback_query
    await query.answer()
    _, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    _, current_days, _, _ = _get_settings_in_days(chat_id)
    context.user_data[f"cln_days_draft_{chat_id}"] = current_days
    await query.edit_message_text(
        _interval_draft_text(current_days),
        reply_markup=_interval_draft_keyboard(chat_id, current_days)
    )


async def adjust_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """➖ / ➕ / ذخیره / لغو برای بازه‌ی روز (فقط پیش‌نویس رو تغییر می‌ده تا زده بشه ذخیره)"""
    query = update.callback_query
    _, chat_id, action = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    draft_key = f"cln_days_draft_{chat_id}"

    if action == "noop":
        await query.answer()
        return

    draft = context.user_data.get(draft_key)
    if draft is None:
        _, draft, _, _ = _get_settings_in_days(chat_id)

    if action == "inc":
        draft = min(draft + 1, 365)
        context.user_data[draft_key] = draft
        await query.answer()
        await query.edit_message_text(
            _interval_draft_text(draft),
            reply_markup=_interval_draft_keyboard(chat_id, draft)
        )
        return

    if action == "dec":
        draft = max(draft - 1, 1)
        context.user_data[draft_key] = draft
        await query.answer()
        await query.edit_message_text(
            _interval_draft_text(draft),
            reply_markup=_interval_draft_keyboard(chat_id, draft)
        )
        return

    if action == "save":
        db.set_cleanup_settings(chat_id, interval_seconds=draft * SECONDS_PER_DAY)
        context.user_data.pop(draft_key, None)
        await query.answer("✔ ذخیره شد")
        await _render_panel(query, chat_id)
        return

    if action == "cancel":
        context.user_data.pop(draft_key, None)
        await query.answer("لغو شد")
        await _render_panel(query, chat_id)
        return


# ---------------------------------------------------------------------------
# تنظیم تعداد پیام با ➖ / ➕ / ذخیره / لغو (+ استفاده‌ی جایگزین با دکمه‌ی آماده)
# ---------------------------------------------------------------------------

def _count_draft_text(draft_count):
    return (
        "🔢 تنظیم تعداد پیام هر پاک‌سازی\n\n"
        f"مقدار در حال تنظیم: {draft_count} پیام\n"
        "(هنوز ذخیره نشده)\n\n"
        "با ➖/➕ عدد رو تغییر بده، بعد «✅ ذخیره» رو بزن."
    )


def _count_draft_keyboard(chat_id, draft_count):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"cln_count_adjust:{chat_id}:dec"),
            InlineKeyboardButton(f"{draft_count} پیام", callback_data=f"cln_count_adjust:{chat_id}:noop"),
            InlineKeyboardButton("➕", callback_data=f"cln_count_adjust:{chat_id}:inc"),
        ],
        [
            InlineKeyboardButton("✅ ذخیره", callback_data=f"cln_count_adjust:{chat_id}:save"),
            InlineKeyboardButton("❌ لغو", callback_data=f"cln_count_adjust:{chat_id}:cancel"),
        ],
    ])


async def adjust_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    باز کردن + تنظیم تعداد پیام با ➖/➕. اولین بار با action == 'open' صدا زده
    می‌شه (از دکمه‌ی پنل اصلی)، و پیش‌نویس رو با مقدار فعلی می‌سازه.
    """
    query = update.callback_query
    _, chat_id, action = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    draft_key = f"cln_count_draft_{chat_id}"

    if action == "open":
        await query.answer()
        _, _, current_count, _ = db.get_cleanup_settings(chat_id)
        context.user_data[draft_key] = current_count
        await query.edit_message_text(
            _count_draft_text(current_count),
            reply_markup=_count_draft_keyboard(chat_id, current_count)
        )
        return

    if action == "noop":
        await query.answer()
        return

    draft = context.user_data.get(draft_key)
    if draft is None:
        _, _, draft, _ = db.get_cleanup_settings(chat_id)

    if action == "inc":
        draft = min(draft + 5, 200)
        context.user_data[draft_key] = draft
        await query.answer()
        await query.edit_message_text(
            _count_draft_text(draft),
            reply_markup=_count_draft_keyboard(chat_id, draft)
        )
        return

    if action == "dec":
        draft = max(draft - 5, 1)
        context.user_data[draft_key] = draft
        await query.answer()
        await query.edit_message_text(
            _count_draft_text(draft),
            reply_markup=_count_draft_keyboard(chat_id, draft)
        )
        return

    if action == "save":
        db.set_cleanup_settings(chat_id, count=draft)
        context.user_data.pop(draft_key, None)
        await query.answer("✔ ذخیره شد")
        await _render_panel(query, chat_id)
        return

    if action == "cancel":
        context.user_data.pop(draft_key, None)
        await query.answer("لغو شد")
        await _render_panel(query, chat_id)
        return


async def set_cleanup_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌های آماده (در صورت استفاده‌ی جای دیگه) برای تعداد پیام - ذخیره‌ی فوری"""
    query = update.callback_query
    _, chat_id, count = query.data.split(":")
    chat_id, count = int(chat_id), int(count)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_cleanup_settings(chat_id, count=count)
    await query.answer("✔ ذخیره شد")
    await _render_panel(query, chat_id)


# ---------------------------------------------------------------------------
# ردیابی آخرین پیام + اجرای خودکار زمان‌بندی‌شده
# ---------------------------------------------------------------------------

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
        enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
        if not enabled:
            continue
        # نکته: interval_seconds از قبل به ثانیه‌ست، دیگه لازم نیست ضربدر 86400 بشه
        if now - last_ts < interval_seconds:
            continue

        last_msg_id = db.get_last_message_id(chat_id)
        if not last_msg_id:
            db.set_cleanup_settings(chat_id, last_ts=now)
            continue

        deleted = await _sweep_oldest_messages(context.bot, chat_id, count)

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
