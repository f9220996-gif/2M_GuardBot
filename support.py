# -*- coding: utf-8 -*-
"""
سیستم پشتیبانی ربات
"""

import time
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from config import CREATOR_ID


# ===== دکمه پشتیبانی در منوی اصلی =====
async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    # اگر کاربر سازنده است → پنل مدیریت پشتیبانی
    if user.id == CREATOR_ID:
        await support_admin_panel(update, context)
        return
    
    # کاربر عادی → فرم ارسال پیام
    await query.edit_message_text(
        "📩 **ارسال پیام به پشتیبانی**\n\n"
        "لطفاً پیام خود را بنویسید.\n"
        "می‌توانید همراه با پیام، عکس هم ارسال کنید.\n\n"
        "⚠️ پیام شما پس از تأیید برای پشتیبانی ارسال می‌شود.\n"
        "برای لغو، دکمه لغو را بزنید.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✘ لغو", callback_data="start_menu")]
        ]),
        parse_mode="Markdown"
    )
    context.user_data["waiting_for_support"] = True
    context.user_data["support_photo"] = None
    context.user_data["support_text"] = None


async def receive_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام پشتیبانی از کاربر (متن یا عکس)"""
    if not context.user_data.get("waiting_for_support"):
        return False
    
    user = update.effective_user
    message = update.effective_message
    
    # ذخیره عکس اگه وجود داشته باشه
    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
        context.user_data["support_photo"] = photo
        await message.reply_text("✔ عکس دریافت شد. حالا متن خود را بنویسید.")
        return True
    
    # ذخیره متن
    if message.text:
        context.user_data["support_text"] = message.text
        
        # ===== دکمه‌های بله/خیر در یک خط (کنار هم) =====
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✔ بله", callback_data=f"support_confirm:{message.message_id}"),
                InlineKeyboardButton("✘ خیر", callback_data="support_cancel"),
            ]
        ])
        # ================================================
        
        await message.reply_text(
            "📩 **تأیید ارسال**\n\n"
            "آیا می‌خواهید این پیام را برای پشتیبانی ارسال کنید؟",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return True
    
    return False


async def confirm_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأیید ارسال پیام به پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
    _, message_id = query.data.split(":")
    user = update.effective_user
    
    # دریافت اطلاعات از context
    photo = context.user_data.get("support_photo")
    text = context.user_data.get("support_text", "")
    
    if not text and not photo:
        await query.edit_message_text("❌ پیامی برای ارسال وجود ندارد.")
        return
    
    # ساخت داده برای ذخیره
    data = {
        "user_id": user.id,
        "username": f"@{user.username}" if user.username else user.full_name,
        "text": text,
        "photo": photo,
        "timestamp": time.time(),
        "status": "pending"
    }
    
    # ذخیره در دیتابیس
    db.set_setting(f"support_msg_{int(time.time())}_{user.id}", json.dumps(data))
    
    # ارسال به سازنده
    admin_text = (
        f"📩 **پیام جدید از پشتیبانی**\n\n"
        f"👤 فرستنده: {data['username']}\n"
        f"🆔 آیدی: {data['user_id']}\n"
        f"🕐 زمان: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"📝 متن:\n{data['text']}"
    )
    
    # ===== دکمه‌های پاسخ/حذف در یک خط (کنار هم) =====
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 پاسخ", callback_data=f"support_reply:{data['user_id']}:{data['timestamp']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"support_delete:{data['user_id']}:{data['timestamp']}"),
        ]
    ])
    # =================================================
    
    try:
        if photo:
            await context.bot.send_photo(
                CREATOR_ID,
                photo=photo,
                caption=admin_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                CREATOR_ID,
                admin_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        
        await query.edit_message_text(
            "✔ پیام شما با موفقیت به پشتیبانی ارسال شد.\n\n"
            "به زودی پاسخ داده خواهد شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
            ])
        )
        
    except Exception as e:
        await query.edit_message_text(f"✘ خطا در ارسال: {e}")
        return
    
    # پاک کردن context
    context.user_data["waiting_for_support"] = False
    context.user_data["support_photo"] = None
    context.user_data["support_text"] = None


async def cancel_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ارسال پیام پشتیبانی و برگشت به پنل اصلی"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for_support"] = False
    context.user_data["support_photo"] = None
    context.user_data["support_text"] = None
    
    # ===== برگشت به پنل اصلی =====
    from start import send_start_panel
    await send_start_panel(update, context)
    # ==============================


# ===== پنل مدیریت پشتیبانی (برای سازنده) =====
async def support_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت پشتیبانی برای سازنده"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    if user.id != CREATOR_ID:
        await query.edit_message_text("⛔️ این بخش فقط برای سازنده است.")
        return
    
    # دریافت لیست پیام‌های پشتیبانی
    keys = db.get_all_keys()
    messages = []
    for key in keys:
        if key.startswith("support_msg_"):
            data = db.get_setting(key, "")
            if data:
                try:
                    msg = json.loads(data)
                    messages.append(msg)
                except:
                    pass
    
    if not messages:
        text = "📩 **پنل پشتیبانی**\n\nهیچ پیامی دریافت نشده است."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
        ])
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return
    
    # ساخت دکمه‌ها برای هر پیام (۲ ستونه)
    rows = []
    for i in range(0, len(messages[:20]), 2):
        row = []
        for j in range(2):
            if i + j < len(messages[:20]):
                msg = messages[i + j]
                username = msg.get('username', 'ناشناس')
                timestamp = time.strftime('%H:%M', time.localtime(msg.get('timestamp', 0)))
                row.append(InlineKeyboardButton(
                    f"{i+j+1}. {username} - {timestamp}",
                    callback_data=f"support_show:{i+j}"
                ))
        rows.append(row)
    
    rows.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="support_admin")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")])
    
    text = f"📩 **پنل پشتیبانی**\n\n{len(messages)} پیام دریافت شده.\n\nروی هرکدام کلیک کنید تا متن را ببینید."
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
    
    # ذخیره لیست پیام‌ها در context
    context.user_data["support_messages"] = messages


async def show_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش یک پیام پشتیبانی به سازنده"""
    query = update.callback_query
    await query.answer()
    
    _, index = query.data.split(":")
    index = int(index)
    
    messages = context.user_data.get("support_messages", [])
    if not messages or index >= len(messages):
        await query.edit_message_text("✘ پیام یافت نشد.")
        return
    
    msg = messages[index]
    
    text = (
        f"📩 **پیام پشتیبانی**\n\n"
        f"👤 فرستنده: {msg.get('username', 'ناشناس')}\n"
        f"🆔 آیدی: {msg.get('user_id', 'نامشخص')}\n"
        f"🕐 زمان: {time.strftime('%Y-%m-%d %H:%M', time.localtime(msg.get('timestamp', 0)))}\n\n"
        f"📝 متن:\n{msg.get('text', 'بدون متن')}"
    )
    
    # ===== دکمه‌های پاسخ/حذف در یک خط (کنار هم) =====
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 پاسخ", callback_data=f"support_reply:{msg['user_id']}:{msg['timestamp']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"support_delete:{msg['user_id']}:{msg['timestamp']}"),
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="support_admin")],
    ])
    # =================================================
    
    if msg.get('photo'):
        await query.edit_message_caption(
            caption=text,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            text,
            reply_markup=kb,
            parse_mode="Markdown"
        )


async def support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به یک پیام پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
    _, user_id, timestamp = query.data.split(":")
    user_id = int(user_id)
    
    await query.edit_message_text(
        f"📩 **پاسخ به پیام**\n\n"
        f"لطفاً متن پاسخ خود را بنویسید.\n"
        f"پاسخ شما به کاربر ارسال خواهد شد.\n\n"
        "برای لغو، /cancel را بفرستید.",
        parse_mode="Markdown"
    )
    
    context.user_data["support_reply_to"] = user_id
    context.user_data["support_reply_timestamp"] = timestamp


async def send_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پاسخ به کاربر"""
    if not context.user_data.get("support_reply_to"):
        return False
    
    user_id = context.user_data["support_reply_to"]
    reply_text = update.effective_message.text
    
    if reply_text == "/cancel":
        context.user_data["support_reply_to"] = None
        await update.effective_message.reply_text("✘ پاسخ لغو شد.")
        return True
    
    try:
        await context.bot.send_message(
            user_id,
            f"📩 **پاسخ پشتیبانی**\n\n{reply_text}\n\n"
            "💡 برای ارسال پیام جدید، دکمه پشتیبانی را بزنید.",
            parse_mode="Markdown"
        )
        await update.effective_message.reply_text("✔ پاسخ با موفقیت ارسال شد.")
    except Exception as e:
        await update.effective_message.reply_text(f"✘ خطا در ارسال: {e}")
    
    context.user_data["support_reply_to"] = None
    return True


async def support_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف پیام پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
    _, user_id, timestamp = query.data.split(":")
    user_id = int(user_id)
    
    # حذف از دیتابیس
    keys = db.get_all_keys()
    for key in keys:
        if key.startswith("support_msg_"):
            data = db.get_setting(key, "")
            if data:
                try:
                    msg = json.loads(data)
                    if msg.get('user_id') == user_id and msg.get('timestamp') == float(timestamp):
                        db.set_setting(key, "")
                        await query.edit_message_text("🗑 پیام با موفقیت حذف شد.")
                        return
                except:
                    pass
    
    await query.edit_message_text("✘ پیام یافت نشد.")
