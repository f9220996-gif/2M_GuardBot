# -*- coding: utf-8 -*-
"""
پیام /start در پی‌وی ربات + دکمه‌های شیشه‌ای (Inline Keyboard)
"""

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import ContextTypes

import database as db
from config import CREATOR_ID
from permissions import is_creator, is_group_owner

START_TEXT = (
    "🤖 سلام! عزیز\n\n"
    "با بهترین ربات مدیریت گروه آشنا شوید\n"
    "دستیار قدرتمند برای نظم و امنیت گروه‌ها\n\n"
    "✨ ویژگی‌های کلیدی\n"
    "✅ پاسخ سریع  •  ✅ گروه‌های بزرگ\n"
    "✅ امنیت بالا  •  ✅ ضداسپم\n"
    "✅ فیلتر کلمات  •  ✅ کنترل دسترسی\n"
    "✅ قفل حرفه‌ای  •  ✅ پشتیبانی سریع\n\n"
    "🚀 نحوه نصب\n"
    "1️⃣ ربات رو به گروهتون اضافه کنید\n"
    "2️⃣ اون رو ادمین کامل کنید تا فعال بشه\n\n"
    "همین حالا ربات را به گروه خود اضافه کنید! 🎯"
)


def build_start_keyboard(user_id: int, bot_username: str):
    rows = [
        [InlineKeyboardButton(
            "➕ افزودن به گروه",
            url=f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users+pin_messages"
        )],
        [
            InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="panel_my_groups"),
            InlineKeyboardButton("📘 راهنما", callback_data="help_commands"),
        ],
    ]
    if user_id == CREATOR_ID:
        rows.append([InlineKeyboardButton("👑 پنل ویژه سازنده", callback_data="creator_panel_open")])
    
    # دکمه ری‌استارت
    rows.append([InlineKeyboardButton("🔄 ری‌استارت ربات", callback_data="restart_bot")])
    
    return InlineKeyboardMarkup(rows)


BACK_STEP_BUTTON_TEXT = "◀️ صفحه قبل"

PERSISTENT_KEYBOARD = ReplyKeyboardMarkup(
    [[BACK_STEP_BUTTON_TEXT]],
    resize_keyboard=True,
    is_persistent=True,
)


async def send_start_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط پنل اصلی (با دکمه‌های شیشه‌ای) رو می‌فرسته"""
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    await update.effective_message.reply_text(
        START_TEXT,
        reply_markup=build_start_keyboard(user.id, bot_username)
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        return

    if not db.is_global_active() and user.id != CREATOR_ID:
        await update.effective_message.reply_text(db.get_shutdown_message())
        return

    await update.effective_message.reply_text(
        "🔽 از دکمه پایین برای رفتن به صفحه قبل استفاده کن.",
        reply_markup=PERSISTENT_KEYBOARD
    )

    await send_start_panel(update, context)


HELP_TEXT = (
    "📘 دستورات گروه (بدون /):\n"
    "🔒 خاموشی [۵h] — قفل گروه\n"
    "🔓 روشن — باز کردن گروه\n"
    "🔇 سکوت [مدت] (ریپلای)\n"
    "🔊 آزاد کن (ریپلای)\n"
    "⛔️ بن کن [دلیل] (ریپلای)\n"
    "🗑 پاک [عدد] (ریپلای) — عدد=چندتا قبلی هم پاک شه\n"
    "🚫 گیف بن / استیکر بن (ریپلای)\n"
    "🚨 گزارش (ریپلای) — برای همه اعضا\n"
    "🌐 ترجمه (ریپلای) یا .متن — ترجمه سریع\n"
    "📅 تاریخ — تاریخ و ساعت شمسی\n"
    "💰 دلار / طلا / اسم رمزارز — قیمت لحظه‌ای\n"
    "💹 رمز ارز — جدول همه قیمت‌ها\n"
    "🎲 بازی: تاس، شیر_یا_خط، سنگ_کاغذ_قیچی، حدس_عدد\n"
    "زمان: 5h=ساعت، 30m=دقیقه، 45s=ثانیه\n\n"
    "🧩 قابلیت‌های روشن/خاموش‌شدنی (از پنل مدیریت هر گروه):\n"
    "فیلتر فحش، بازی‌ها، ارسال گیف/استیکر/عکس/فیلم/فایل، "
    "دستور تاریخ، دستور دلار\n\n"
    "⚙️ امکانات دیگه پنل: خوش‌آمدگویی، ویرایش اخطارها، "
    "پاک‌سازی خودکار، زبان ترجمه، بن‌شده‌ها/سکوت‌خورده‌ها/اخطارها/گزارش‌ها"
)


async def on_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
    ])
    await query.message.reply_text(HELP_TEXT, reply_markup=kb)


# ===== تابع ری‌استارت =====
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ری‌استارت ربات (فقط برای سازنده)"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.edit_message_text("⛔️ فقط سازنده ربات می‌تونه ری‌استارت کنه.")
        return
    
    await query.edit_message_text("🔄 ربات در حال ری‌استارت...")
    
    # ری‌استارت واقعی برای Railway
    import sys
    import os
    os.execv(sys.executable, ['python'] + sys.argv)
# ============================
