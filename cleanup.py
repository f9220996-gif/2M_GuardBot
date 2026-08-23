# -*- coding: utf-8 -*-
"""
پاک‌سازی خودکار پیام‌های قدیمی گروه
"""

import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_admin


async def open_cleanup_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل پاک‌سازی خودکار با قابلیت تنظیم دلخواه"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    # دریافت تنظیمات
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    
    # محاسبه روز/ساعت/دقیقه از ثانیه
    days = interval_seconds // 86400
    hours = (interval_seconds % 86400) // 3600
    minutes = (interval_seconds % 3600) // 60
    
    # ساخت متن
    status = "✔ فعال" if enabled else "✘ غیرفعال"
    if enabled:
        time_str = f"{days} روز {hours} ساعت {minutes} دقیقه"
    else:
        time_str = "تنظیم نشده"
    
    text = (
        f"🧹 **پاک‌سازی خودکار**\n\n"
        f"وضعیت: {status}\n"
        f"بازه زمانی: {time_str}\n"
        f"تعداد پیام: {count}\n"
        f"آخرین پاک‌سازی: {'-' if last_ts == 0 else datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M')}\n\n"
        "با دکمه‌های زیر تنظیمات را تغییر دهید:"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 روشن/خاموش", callback_data=f"cln_toggle:{chat_id}"),
        ],
        [
            InlineKeyboardButton("📅 روز", callback_data=f"cln_interval:{chat_id}:days"),
            InlineKeyboardButton("🕐 ساعت", callback_data=f"cln_interval:{chat_id}:hours"),
            InlineKeyboardButton("⏱ دقیقه", callback_data=f"cln_interval:{chat_id}:minutes"),
        ],
        [
            InlineKeyboardButton("📊 تعداد پیام", callback_data=f"cln_count:{chat_id}"),
        ],
        [
            InlineKeyboardButton("🔄 اجرای الان", callback_data=f"cln_run:{chat_id}"),
        ],
        [
            InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}"),
        ],
    ])
    
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def toggle_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """روشن/خاموش کردن پاک‌سازی"""
    query = update.callback_query
    _, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    db.set_cleanup_settings(chat_id, enabled=not enabled)
    
    await query.answer("✔ ذخیره شد")
    await open_cleanup_panel(update, context)


async def adjust_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغییر بازه زمانی با دکمه‌های + و -"""
    query = update.callback_query
    _, chat_id, unit, action = query.data.split(":")
    chat_id = int(chat_id)
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    # دریافت تنظیمات فعلی
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    
    # مقادیر هر واحد به ثانیه
    unit_map = {
        "days": 86400,
        "hours": 3600,
        "minutes": 60,
    }
    step = unit_map.get(unit, 3600)
    
    if action == "plus":
        interval_seconds += step
    elif action == "minus":
        interval_seconds = max(60, interval_seconds - step)  # حداقل ۱ دقیقه
    
    # ذخیره
    db.set_cleanup_settings(chat_id, interval_seconds=interval_seconds)
    
    await query.answer("✔ ذخیره شد")
    await open_cleanup_panel(update, context)


async def set_cleanup_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغییر تعداد پیام‌ها با دکمه‌های + و -"""
    query = update.callback_query
    _, chat_id, action = query.data.split(":")
    chat_id = int(chat_id)
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    
    if action == "plus":
        count = min(200, count + 10)
    elif action == "minus":
        count = max(5, count - 10)
    
    db.set_cleanup_settings(chat_id, count=count)
    
    await query.answer("✔ ذخیره شد")
    await open_cleanup_panel(update, context)


async def run_cleanup_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای فوری پاک‌سازی"""
    query = update.callback_query
    _, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    await query.answer("🔄 در حال پاک‌سازی...")
    
    # اجرای پاک‌سازی
    await do_cleanup(context.bot, chat_id)
    db.set_cleanup_settings(chat_id, last_ts=time.time())
    
    await open_cleanup_panel(update, context)


async def do_cleanup(bot, chat_id):
    """انجام پاک‌سازی پیام‌ها"""
    try:
        enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
        last_msg_id = db.get_last_message_id(chat_id)
        
        if not last_msg_id:
            return
        
        # پیدا کردن پیام‌های قدیمی‌تر از آخرین پیام
        # (توی تلگرام نمی‌تونیم مستقیم بر اساس زمان پاک کنیم،
        # باید آخرین پیام رو پیدا کنیم و از اون به عقب پاک کنیم)
        
        deleted = 0
        msg_id = last_msg_id
        while deleted < count and msg_id > 0:
            try:
                await bot.delete_message(chat_id, msg_id)
                deleted += 1
            except Exception:
                pass
            msg_id -= 1
        
        # به‌روزرسانی آخرین پیام
        db.update_last_message_id(chat_id, last_msg_id - deleted)
        
        if deleted > 0:
            await bot.send_message(chat_id, f"🧹 {deleted} پیام قدیمی پاک شد.")
            
    except Exception as e:
        print(f"Cleanup Error: {e}")


async def run_auto_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """Job دوره‌ای که هر ساعت چک می‌کنه کدوم گروه‌ها زمان پاک‌سازی‌شون رسیده"""
    chat_ids = db.get_all_cleanup_enabled_chats()
    now = time.time()
    
    for chat_id in chat_ids:
        enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
        if not enabled:
            continue
        
        # چک کن که آیا زمان پاک‌سازی رسیده یا نه
        if now - last_ts >= interval_seconds:
            await do_cleanup(context.bot, chat_id)
            db.set_cleanup_settings(chat_id, last_ts=now)


async def track_last_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ذخیره آخرین آیدی پیام هر گروه"""
    chat = update.effective_chat
    message = update.effective_message
    if chat and message and chat.type in ("group", "supergroup"):
        db.update_last_message_id(chat.id, message.message_id)


async def ask_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش دکمه‌های تنظیم بازه زمانی"""
    query = update.callback_query
    _, chat_id, unit = query.data.split(":")
    chat_id = int(chat_id)
    
    await query.answer()
    
    # دریافت مقدار فعلی
    enabled, interval_seconds, count, last_ts = db.get_cleanup_settings(chat_id)
    
    # محاسبه مقدار بر حسب واحد انتخاب شده
    unit_map = {
        "days": ("روز", 86400),
        "hours": ("ساعت", 3600),
        "minutes": ("دقیقه", 60),
    }
    label, divisor = unit_map.get(unit, ("ساعت", 3600))
    value = interval_seconds // divisor
    
    text = f"⏱ **تنظیم {label}**\n\nمقدار فعلی: {value} {label}\n\nبا دکمه‌های زیر تنظیم کنید:"
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"cln_adjust:{chat_id}:{unit}:minus"),
            InlineKeyboardButton(f"{value}", callback_data="cln_dummy"),
            InlineKeyboardButton("➕", callback_data=f"cln_adjust:{chat_id}:{unit}:plus"),
        ],
        [
            InlineKeyboardButton("⬅️ بازگشت", callback_data=f"cln_panel:{chat_id}"),
        ],
    ])
    
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
