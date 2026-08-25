# -*- coding: utf-8 -*-
"""
پنل ویژه سازنده ربات
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from config import CREATOR_ID


async def open_creator_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل ویژه سازنده"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        if query:
            await query.edit_message_text("⛔️ این پنل فقط برای سازنده ربات است.")
        else:
            await update.effective_message.reply_text("⛔️ این پنل فقط برای سازنده ربات است.")
        return
    
    # دریافت وضعیت‌ها
    is_active = db.is_global_active()
    shutdown_msg = db.get_shutdown_message()
    update_msg = db.get_setting("update_message", "⚠️ ربات آپدیت شده است! لطفاً ربات را دوباره به گروه اضافه کنید و ادمین کامل کنید.")
    
    text = (
        "👑 **پنل ویژه سازنده**\n\n"
        f"وضعیت ربات: {'🟢 فعال' if is_active else '🔴 خاموش'}\n"
        f"پیام خاموشی: {shutdown_msg[:40]}{'...' if len(shutdown_msg) > 40 else ''}\n"
        f"پیام آپدیت: {update_msg[:40]}{'...' if len(update_msg) > 40 else ''}\n\n"
        "از دکمه‌های زیر برای مدیریت استفاده کنید:"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔴 خاموش" if is_active else "🟢 روشن",
                callback_data="creator_global_off" if is_active else "creator_global_on"
            ),
            InlineKeyboardButton("📝 خاموشی", callback_data="creator_set_msg"),
        ],
        [
            InlineKeyboardButton("📝 آپدیت", callback_data="creator_set_update_msg"),
            InlineKeyboardButton("📋 نمایش آپدیت", callback_data="creator_show_update_msg"),
        ],
        [
            InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu"),
        ],
    ])
    
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def toggle_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """روشن/خاموش کردن سراسری ربات"""
    query = update.callback_query
    _, action = query.data.split(":")
    user = update.effective_user
    
    if user.id != CREATOR_ID:
        await query.answer("⛔️ فقط سازنده", show_alert=True)
        return
    
    db.set_global_active(action == "on")
    await query.answer("✔ ذخیره شد")
    await open_creator_panel(update, context)


# ===== تنظیم پیام خاموشی =====
async def ask_set_shutdown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست متن جدید برای پیام خاموشی"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.answer("⛔️ فقط سازنده", show_alert=True)
        return
    
    # ===== دکمه بازگشت =====
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="creator_panel_open")]
    ])
    # ========================
    
    # ===== ویرایش پیام فعلی =====
    await query.edit_message_text(
        "📝 **تغییر پیام خاموشی**\n\n"
        "لطفاً متن جدید پیام خاموشی را ارسال کنید.\n"
        "این پیام زمانی که ربات خاموش است به کاربران نمایش داده می‌شود.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    # =============================
    
    context.user_data["waiting_for_shutdown_text"] = True


async def receive_shutdown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید پیام خاموشی"""
    if not context.user_data.get("waiting_for_shutdown_text"):
        return False
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        return False
    
    text = update.effective_message.text
    if text == "/cancel":
        context.user_data["waiting_for_shutdown_text"] = False
        await update.effective_message.reply_text("❌ لغو شد.")
        return True
    
    db.set_shutdown_message(text)
    context.user_data["waiting_for_shutdown_text"] = False
    
    # ===== بعد از تغییر، برگرد به پنل سازنده =====
    await update.effective_message.reply_text("✔ پیام خاموشی با موفقیت تغییر کرد!")
    # ===== ارسال مجدد پنل سازنده =====
    await open_creator_panel(update, context)
    # ================================
    
    return True


# ===== تنظیم پیام آپدیت =====
async def ask_set_update_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست متن جدید برای پیام آپدیت"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.answer("⛔️ فقط سازنده", show_alert=True)
        return
    
    # ===== دکمه بازگشت =====
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="creator_panel_open")]
    ])
    # ========================
    
    # ===== ویرایش پیام فعلی =====
    await query.edit_message_text(
        "📝 **تغییر پیام آپدیت**\n\n"
        "لطفاً متن جدید پیام آپدیت را ارسال کنید.\n"
        "این پیام زمانی که ربات آپدیت می‌شود به مدیران گروه نمایش داده می‌شود.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    # =============================
    
    context.user_data["waiting_for_update_msg"] = True


async def receive_update_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید پیام آپدیت"""
    if not context.user_data.get("waiting_for_update_msg"):
        return False
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        return False
    
    text = update.effective_message.text
    if text == "/cancel":
        context.user_data["waiting_for_update_msg"] = False
        await update.effective_message.reply_text("❌ لغو شد.")
        return True
    
    db.set_setting("update_message", text)
    context.user_data["waiting_for_update_msg"] = False
    
    # ===== بعد از تغییر، برگرد به پنل سازنده =====
    await update.effective_message.reply_text("✔ پیام آپدیت با موفقیت تغییر کرد!")
    # ===== ارسال مجدد پنل سازنده =====
    await open_creator_panel(update, context)
    # ================================
    
    return True


async def show_update_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پیام آپدیت فعلی"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.answer("⛔️ فقط سازنده", show_alert=True)
        return
    
    msg = db.get_setting("update_message", "⚠️ ربات آپدیت شده است! لطفاً ربات را دوباره به گروه اضافه کنید و ادمین کامل کنید.")
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="creator_panel_open")]
    ])
    
    await query.edit_message_text(
        f"📋 **پیام آپدیت فعلی:**\n\n{msg}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
