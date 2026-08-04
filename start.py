# -*- coding: utf-8 -*-
"""
پیام /start در پی‌وی ربات + دکمه‌های شیشه‌ای (Inline Keyboard)
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from config import CREATOR_ID
from permissions import is_creator, is_group_owner

START_TEXT = (
    "🤖 سلام! عزیز\n\n"
    "با بهترین ربات مدیریت گروه آشنا شوید\n\n"
    "دستیار قدرتمند برای نظم و امنیت گروه‌ها\n"
    "حرفه‌ای‌ترین ابزار کنترل در دست شماست\n\n"
    "───\n\n"
    "✨ ویژگی‌های کلیدی\n\n"
    "✅ پاسخ‌دهی سریع به دستورات\n"
    "✅ عملکرد بی‌نقص حتی در گروه‌های بزرگ\n"
    "✅ پایداری کامل بدون قطعی\n"
    "✅ امنیت و محافظت از گروه\n"
    "✅ جلوگیری از اسپم و پیام‌های مزاحم\n"
    "✅ فیلتر پیشرفته کلمات و عبارات\n"
    "✅ کنترل دقیق دسترسی اعضا\n"
    "✅ ابزارهای متنوع و کاربردی\n"
    "✅ سیستم قفل و محدودیت حرفه‌ای\n"
    "✅ پشتیبانی اختصاصی و سریع\n"
    "✅ نصب و راه‌اندازی آسان\n"
    "✅ آپدیت‌های منظم با قابلیت‌های جدید\n\n"
    "───\n\n"
    "🚀 نحوه نصب\n\n"
    "1️⃣ ربات رو به گروهتون اضافه کنید\n"
    "2️⃣ اون رو ادمین کنید تا فعال بشه\n\n"
    "───\n\n"
    "⚠️ نکات مهم\n\n"
    "🔹 دسترسی کامل ادمین رو بهش بدید تا کارش درست انجام بده\n\n"
    "───\n\n"
    "همین حالا ربات را به گروه خود اضافه کنید! 🎯🤖"
)


def build_start_keyboard(user_id: int, bot_username: str):
    rows = [
        [InlineKeyboardButton(
            "➕ افزودن ربات به گروه",
            url=f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users+pin_messages"
        )],
        [InlineKeyboardButton("⚙️ پنل مدیریت گروه‌های من", callback_data="panel_my_groups")],
        [InlineKeyboardButton("📘 راهنمای دستورات", callback_data="help_commands")],
    ]
    if user_id == CREATOR_ID:
        rows.append([InlineKeyboardButton("👑 پنل ویژه سازنده", callback_data="creator_panel_open")])
    return InlineKeyboardMarkup(rows)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        return  # فقط در پی‌وی پیام خوش‌آمد نشون بده

    # چک خاموشی سراسری ربات (به جز سازنده)
    if not db.is_global_active() and user.id != CREATOR_ID:
        await update.effective_message.reply_text(db.get_shutdown_message())
        return

    bot_username = (await context.bot.get_me()).username
    await update.effective_message.reply_text(
        START_TEXT,
        reply_markup=build_start_keyboard(user.id, bot_username)
    )


HELP_TEXT = (
    "📘 راهنمای دستورات (داخل گروه):\n\n"
    "🔒 خاموشی [مدت اختیاری مثل 5h] — قفل گروه\n"
    "🔓 روشن — باز کردن فوری گروه\n"
    "🔇 سکوت [مدت] (ریپلای) — سکوت کاربر\n"
    "🔊 آزاد کن (ریپلای) — برداشتن سکوت\n"
    "⛔️ بن کن [دلیل] (ریپلای) — بن کامل کاربر\n"
    "🗑 پاک (ریپلای) — حذف پیام\n"
    "🚫 گیف بن (ریپلای روی گیف)\n"
    "🚫 استیکر بن (ریپلای روی استیکر)\n\n"
    "🎲 بازی‌ها: تاس ، شیر_یا_خط ، سنگ_کاغذ_قیچی [سنگ/کاغذ/قیچی] ، حدس_عدد ، حدس [عدد]\n\n"
    "مثال زمان: 5h = ۵ ساعت, 30m = ۳۰ دقیقه, 45s = ۴۵ ثانیه (قابل ترکیب: 1h30m)"
)


async def on_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(HELP_TEXT)
