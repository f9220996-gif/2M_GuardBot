# -*- coding: utf-8 -*-
"""
تنظیمات خوش‌آمدگویی به اعضای جدید
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_admin
from persian_date import now_tehran


async def on_new_member_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی عضو جدید به گروه اضافه میشه، پیام خوش‌آمدگویی بفرست"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.new_chat_members:
        return
    
    if not db.is_global_active():
        return
    
    if not db.is_feature_enabled(chat.id, "welcome"):
        return
    
    for new_member in message.new_chat_members:
        me = await context.bot.get_me()
        if new_member.id == me.id:
            return
        
        welcome_text = db.get_welcome_text(chat.id)
        
        user_name = new_member.full_name or new_member.username or "کاربر"
        group_name = chat.title or "گروه"
        now = now_tehran()
        date_str = now.strftime("%Y/%m/%d")
        time_str = now.strftime("%H:%M")
        
        welcome_text = welcome_text.replace("{user}", user_name)
        welcome_text = welcome_text.replace("{group}", group_name)
        welcome_text = welcome_text.replace("{date}", date_str)
        welcome_text = welcome_text.replace("{time}", time_str)
        
        sticker_id, gif_id = db.get_welcome_media(chat.id)
        
        try:
            if sticker_id:
                await context.bot.send_sticker(chat.id, sticker_id)
            elif gif_id:
                await context.bot.send_animation(chat.id, gif_id)
            
            await context.bot.send_message(chat.id, welcome_text)
        except Exception:
            try:
                await context.bot.send_message(chat.id, welcome_text)
            except Exception:
                pass


async def open_welcome_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل تنظیمات خوش‌آمدگویی"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    enabled = db.is_feature_enabled(chat_id, "welcome")
    welcome_text = db.get_welcome_text(chat_id)
    sticker_id, gif_id = db.get_welcome_media(chat_id)
    
    text = (
        "👋 **تنظیمات خوش‌آمدگویی**\n\n"
        f"وضعیت: {'✔ فعال' if enabled else '✘ غیرفعال'}\n"
        f"متن فعلی: {welcome_text[:50]}{'...' if len(welcome_text) > 50 else ''}\n"
        f"مدیا: {'🎬 استیکر' if sticker_id else '🎞 گیف' if gif_id else '❌ بدون مدیا'}\n\n"
        "از دکمه‌های زیر برای تنظیم استفاده کنید:"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 روشن/خاموش",
                callback_data=f"wc_on:{chat_id}" if not enabled else f"wc_off:{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton("📝 ویرایش متن", callback_data=f"wc_edit:{chat_id}"),
            InlineKeyboardButton("➕ افزودن مدیا", callback_data=f"wc_media:{chat_id}"),
        ],
        [
            InlineKeyboardButton("👀 پیش‌نمایش", callback_data=f"wc_preview:{chat_id}"),
            InlineKeyboardButton("↩️ بازنشانی", callback_data=f"wc_reset:{chat_id}"),
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])
    
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def toggle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """روشن/خاموش کردن خوش‌آمدگویی"""
    query = update.callback_query
    _, action, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    db.set_feature_enabled(chat_id, "welcome", action == "on")
    await query.answer("✔ ذخیره شد")
    await open_welcome_panel(update, context)


async def ask_edit_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست متن جدید برای خوش‌آمدگویی"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    # ===== دکمه بازگشت =====
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"wc_panel:{chat_id}")]
    ])
    # ========================
    
    await query.edit_message_text(
        "📝 **ویرایش متن خوش‌آمدگویی**\n\n"
        "لطفاً متن جدید را ارسال کنید.\n\n"
        "متغیرهای قابل استفاده:\n"
        "• `{user}` — نام کاربر\n"
        "• `{group}` — نام گروه\n"
        "• `{date}` — تاریخ امروز\n"
        "• `{time}` — ساعت امروز\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    context.user_data["waiting_for_welcome_text"] = chat_id


async def receive_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید خوش‌آمدگویی"""
    if not context.user_data.get("waiting_for_welcome_text"):
        return False
    
    chat_id = context.user_data["waiting_for_welcome_text"]
    user = update.effective_user
    
    if not await is_admin(context.bot, chat_id, user.id):
        return False
    
    text = update.effective_message.text
    if text == "/cancel":
        context.user_data["waiting_for_welcome_text"] = None
        await update.effective_message.reply_text("❌ لغو شد.")
        return True
    
    db.set_welcome_text(chat_id, text)
    context.user_data["waiting_for_welcome_text"] = None
    await update.effective_message.reply_text("✔ متن خوش‌آمدگویی با موفقیت تغییر کرد!")
    await open_welcome_panel(update, context)
    return True


async def ask_add_welcome_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست مدیا برای خوش‌آمدگویی"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    # ===== دکمه بازگشت =====
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"wc_panel:{chat_id}")]
    ])
    # ========================
    
    # ===== حذف پیام‌های قبلی =====
    try:
        await query.message.delete()
    except Exception:
        pass
    # =============================
    
    await update.effective_message.reply_text(
        "🎬 **افزودن مدیا به خوش‌آمدگویی**\n\n"
        "یک استیکر یا گیف (GIF) برای خوش‌آمدگویی ارسال کنید.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    context.user_data["waiting_for_welcome_media"] = chat_id


async def receive_welcome_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مدیا برای خوش‌آمدگویی"""
    if not context.user_data.get("waiting_for_welcome_media"):
        return False
    
    chat_id = context.user_data["waiting_for_welcome_media"]
    user = update.effective_user
    
    if not await is_admin(context.bot, chat_id, user.id):
        return False
    
    message = update.effective_message
    msg_id = message.message_id
    
    if message.sticker:
        file_id = message.sticker.file_id
        db.set_welcome_media(chat_id, sticker_file_id=file_id)
        await update.effective_message.reply_text("✔ استیکر با موفقیت ذخیره شد!")
    elif message.animation:
        file_id = message.animation.file_id
        db.set_welcome_media(chat_id, animation_file_id=file_id)
        await update.effective_message.reply_text("✔ گیف با موفقیت ذخیره شد!")
    else:
        await update.effective_message.reply_text("❌ لطفاً یک استیکر یا گیف ارسال کنید.")
        return True
    
    context.user_data["waiting_for_welcome_media"] = None
    
    # ===== حذف پیام‌های قبلی (مدیا و پیام‌های قدیمی) =====
    try:
        # حذف پیام مدیا
        await context.bot.delete_message(chat_id, msg_id)
        # حذف پیام راهنما (آخرین پیام)
        # این کار توسط دکمه بازگشت انجام میشه
    except Exception:
        pass
    # =====================================================
    
    # ===== ارسال مجدد پنل خوش‌آمدگویی =====
    await open_welcome_panel(update, context)
    # =====================================
    
    return True


async def clear_welcome_media_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاک کردن مدیا خوش‌آمدگویی"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    db.clear_welcome_media(chat_id)
    await query.answer("✔ مدیا پاک شد")
    await open_welcome_panel(update, context)


async def preview_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیش‌نمایش پیام خوش‌آمدگویی"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    welcome_text = db.get_welcome_text(chat_id)
    sticker_id, gif_id = db.get_welcome_media(chat_id)
    
    preview_text = welcome_text.replace("{user}", "کاربر نمونه")
    preview_text = preview_text.replace("{group}", "گروه نمونه")
    preview_text = preview_text.replace("{date}", "۱۴۰۴/۰۱/۰۱")
    preview_text = preview_text.replace("{time}", "۱۲:۰۰")
    
    try:
        if sticker_id:
            await context.bot.send_sticker(chat_id, sticker_id)
        elif gif_id:
            await context.bot.send_animation(chat_id, gif_id)
        
        await context.bot.send_message(chat_id, f"👀 **پیش‌نمایش خوش‌آمدگویی:**\n\n{preview_text}", parse_mode="Markdown")
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ خطا در ارسال پیش‌نمایش: {e}")
    
    await query.answer("پیش‌نمایش ارسال شد ✔")


async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازنشانی خوش‌آمدگویی به حالت پیش‌فرض"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    
    user = update.effective_user
    if not await is_admin(context.bot, chat_id, user.id):
        await query.answer("✘ شما اجازه ندارید.", show_alert=True)
        return
    
    db.reset_welcome_text(chat_id)
    db.clear_welcome_media(chat_id)
    await query.answer("✔ بازنشانی شد")
    await open_welcome_panel(update, context)
