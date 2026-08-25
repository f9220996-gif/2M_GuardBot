# -*- coding: utf-8 -*-
"""
پیام /start در پی‌وی ربات + دکمه‌های شیشه‌ای (Inline Keyboard)
"""

import os
import sys
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import database as db
from config import CREATOR_ID

START_TEXT = (
    "🤖 سلام! عزیز\n\n"
    "با بهترین ربات مدیریت گروه آشنا شوید\n"
    "دستیار قدرتمند برای نظم و امنیت گروه‌ها\n\n"
    "✨ ویژگی‌های کلیدی\n"
    "✔ پاسخ سریع  •  ✔ گروه‌های بزرگ\n"
    "✔ امنیت بالا  •  ✔ ضداسپم\n"
    "✔ فیلتر کلمات  •  ✔ کنترل دسترسی\n"
    "✔ قفل حرفه‌ای  •  ✔ پشتیبانی سریع\n\n"
    "🚀 نحوه نصب\n"
    "1️⃣ ربات رو به گروهتون اضافه کنید\n"
    "2️⃣ اون رو ادمین کامل کنید تا فعال بشه\n\n"
    "همین حالا ربات را به گروه خود اضافه کنید! 🎯"
)

WELCOME_TEXT = (
    "🎉 **به ربات مدیریت گروه خوش آمدید!**\n\n"
    "من اینجا هستم تا به شما در مدیریت گروه‌های تلگرام کمک کنم.\n\n"
    "✅ با استفاده از دکمه‌های زیر می‌توانید:\n"
    "• گروه‌های خود را مدیریت کنید\n"
    "• از هوش مصنوعی کمک بگیرید\n"
    "• با پشتیبانی تماس بگیرید\n\n"
    "🌟 **نکته:** ربات را در گروه خود ادمین کامل کنید تا همه قابلیت‌ها فعال شوند."
)

def build_start_keyboard(user_id: int, bot_username: str):
    rows = [
        [InlineKeyboardButton("➕ افزودن به گروه", url=f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users+pin_messages")],
        [InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="panel_my_groups"), InlineKeyboardButton("📘 راهنما", callback_data="help_commands")],
    ]
    if user_id == CREATOR_ID:
        rows.append([InlineKeyboardButton("👑 پنل ویژه سازنده", callback_data="creator_panel_open")])
    rows.append([
        InlineKeyboardButton("🧠 هوش مصنوعی", callback_data="ai_model_select"),
        InlineKeyboardButton("📩 پشتیبانی", callback_data="support_menu"),
    ])
    rows.append([InlineKeyboardButton("🔄 ری‌استارت ربات", callback_data="restart_bot")])
    return InlineKeyboardMarkup(rows)

async def send_start_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    
    is_first_time = db.get_setting(f"first_start_{user.id}", "true") == "true"
    
    if is_first_time:
        db.set_setting(f"first_start_{user.id}", "false")
        await update.effective_message.reply_text(
            WELCOME_TEXT,
            reply_markup=build_start_keyboard(user.id, bot_username),
            parse_mode="Markdown"
        )
    else:
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
        "🤖",
        reply_markup=ReplyKeyboardRemove()
    )
    await send_start_panel(update, context)

HELP_TEXT = (
    "🤖 **راهنمای کامل ربات**\n\n"
    "🔹 **دستورات مدیریت گروه (بدون /):**\n"
    "• `خاموشی [مدت]` — قفل گروه (مثال: خاموشی 2h)\n"
    "• `روشن` — باز کردن گروه\n"
    "• `سکوت [مدت]` (ریپلای) — سکوت کاربر\n"
    "• `آزاد کن` (ریپلای) — آزاد کردن کاربر\n"
    "• `بن کن [دلیل]` (ریپلای) — بن کاربر\n"
    "• `پاک [عدد]` (ریپلای) — پاک کردن پیام‌ها\n"
    "• `گیف بن` / `استیکر بن` (ریپلای) — مسدود کردن مدیا\n\n"
    "🔹 **دستورات کاربری:**\n"
    "• `تاس` — پرتاب تاس\n"
    "• `شیر_یا_خط` — شیر یا خط\n"
    "• `سنگ_کاغذ_قیچی` — بازی\n"
    "• `حدس_عدد` — بازی حدس عدد\n"
    "• `تاریخ` — تاریخ و ساعت شمسی\n"
    "• `رمز ارز` — جدول قیمت‌ها\n"
    "• `گزارش` (ریپلای) — گزارش کاربر به مدیر\n\n"
    "🔹 **قابلیت‌های هوش مصنوعی 🧠:**\n"
    "• پاسخ به سوالات عمومی (فارسی و انگلیسی)\n"
    "• تشخیص و فیلتر هوشمند فحش و توهین\n"
    "• درک مکالمه و پاسخ‌های طبیعی\n"
    "• ترجمه متن به زبان‌های مختلف\n"
    "• محاسبات ریاضی ساده\n"
    "• اطلاعات عمومی (تاریخ، آب و هوا، قیمت‌ها)\n\n"
    "⚙️ **محدودیت‌های هوش مصنوعی:**\n"
    "• حداکثر ۵۰ سوال در روز برای هر کاربر\n"
    "• طول پاسخ حداکثر ۴۰۰۰ کاراکتر\n"
    "• فقط در گروه و پی‌وی ربات قابل استفاده است\n\n"
    "🔹 **نکته مهم:**\n"
    "ربات را ادمین کامل کنید تا همه قابلیت‌ها فعال شوند."
)

async def on_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]])
    await query.message.reply_text(HELP_TEXT, reply_markup=kb, parse_mode="Markdown")

async def ai_model_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Gemini (Google)", callback_data="ai_use_gemini")],
        [InlineKeyboardButton("🤖 ChatGPT (OpenAI)", callback_data="ai_use_chatgpt")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")],
    ])
    
    await query.edit_message_text(
        "🧠 **انتخاب هوش مصنوعی**\n\n"
        "لطفاً مدل مورد نظر را انتخاب کنید:\n\n"
        "• **Gemini** — رایگان، مناسب برای استفاده روزمره\n"
        "• **ChatGPT** — قدرتمندتر، نیاز به کلید API دارد",
        reply_markup=kb,
        parse_mode="Markdown"
    )

async def ai_use_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["ai_model"] = "gemini"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]])
    await query.edit_message_text(
        "✔ **مدل Gemini فعال شد**\n\n"
        "حالا می‌توانید سوال خود را بپرسید.\n"
        "برای شروع، پیام خود را ارسال کنید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

async def ai_use_chatgpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["ai_model"] = "chatgpt"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]])
    await query.edit_message_text(
        "✔ **مدل ChatGPT فعال شد**\n\n"
        "حالا می‌توانید سوال خود را بپرسید.\n"
        "برای شروع، پیام خود را ارسال کنید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ===== ری‌استارت برای همه (بدون محدودیت سازنده) =====
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ری‌استارت ربات (برای همه کاربران)"""
    query = update.callback_query
    await query.answer()
    
    # ===== حذف پیام دکمه ری‌استارت =====
    try:
        await query.message.delete()
    except Exception:
        pass
    # ===================================
    
    # ===== ارسال پنل اصلی =====
    await update.effective_message.reply_text(
        "🤖 خوش آمدید!",
        reply_markup=ReplyKeyboardRemove()
    )
    await send_start_panel(update, context)
    # ===========================
    
    # ===== ری‌استارت واقعی در پس‌زمینه =====
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ خطا در ری‌استارت: {e}")
    # ========================================
