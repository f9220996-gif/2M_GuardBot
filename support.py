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


def _support_prompt_text(extra_line=None):
    text = (
        "📩 **ارسال پیام به پشتیبانی**\n\n"
        "لطفاً پیام خود را بنویسید.\n"
        "می‌توانید همراه با پیام، عکس هم ارسال کنید.\n\n"
        "⚠️ پیام شما پس از تأیید برای پشتیبانی ارسال می‌شود.\n"
        "برای لغو، دکمه لغو را بزنید."
    )
    if extra_line:
        text = f"{extra_line}\n\n{text}"
    return text


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
        _support_prompt_text(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✘ لغو", callback_data="start_menu")]
        ]),
        parse_mode="Markdown"
    )
    context.user_data["waiting_for_support"] = True
    context.user_data["support_photo"] = None
    context.user_data["support_text"] = None
    # آیدی همین پیام رو ذخیره می‌کنیم تا مراحل بعدی (دریافت عکس/متن) رو
    # به‌جای ساختن پیام جدید، رو همینو ویرایش کنیم
    context.user_data["support_prompt_chat_id"] = query.message.chat_id
    context.user_data["support_prompt_message_id"] = query.message.message_id


async def _edit_support_prompt(context, text, kb, parse_mode="Markdown"):
    """پیام پرامپت پشتیبانی رو ویرایش می‌کنه؛ اگه ممکن نبود، پیام جدید می‌فرسته"""
    prompt_chat_id = context.user_data.get("support_prompt_chat_id")
    prompt_message_id = context.user_data.get("support_prompt_message_id")
    if prompt_chat_id and prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=prompt_chat_id, message_id=prompt_message_id,
                text=text, reply_markup=kb, parse_mode=parse_mode
            )
            return
        except Exception:
            pass
    sent = await context.bot.send_message(prompt_chat_id, text, reply_markup=kb, parse_mode=parse_mode)
    context.user_data["support_prompt_chat_id"] = sent.chat_id
    context.user_data["support_prompt_message_id"] = sent.message_id


async def receive_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام پشتیبانی از کاربر (متن یا عکس)"""
    if not context.user_data.get("waiting_for_support"):
        return False
    
    message = update.effective_message
    
    # ذخیره عکس اگه وجود داشته باشه
    if message.photo:
        context.user_data["support_photo"] = message.photo[-1].file_id
        try:
            await message.delete()
        except Exception:
            pass
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✘ لغو", callback_data="start_menu")]])
        await _edit_support_prompt(
            context, _support_prompt_text("✔ عکس دریافت شد. حالا متن خود را بنویسید."), kb
        )
        return True
    
    # ذخیره متن
    if message.text:
        context.user_data["support_text"] = message.text
        try:
            await message.delete()
        except Exception:
            pass

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✔ بله", callback_data=f"support_confirm:{message.message_id}"),
                InlineKeyboardButton("✘ خیر", callback_data="support_cancel"),
            ]
        ])
        await _edit_support_prompt(
            context,
            "📩 **تأیید ارسال**\n\n"
            "آیا می‌خواهید این پیام را برای پشتیبانی ارسال کنید؟",
            kb
        )
        return True
    
    return False


async def confirm_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأیید ارسال پیام به پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
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
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 پاسخ", callback_data=f"support_reply:{data['user_id']}:{data['timestamp']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"support_delete:{data['user_id']}:{data['timestamp']}"),
        ]
    ])
    
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
    context.user_data.pop("support_prompt_chat_id", None)
    context.user_data.pop("support_prompt_message_id", None)


async def cancel_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ارسال پیام پشتیبانی و برگشت به پنل اصلی"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_for_support"] = False
    context.user_data["support_photo"] = None
    context.user_data["support_text"] = None
    context.user_data.pop("support_prompt_chat_id", None)
    context.user_data.pop("support_prompt_message_id", None)
    
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
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 پاسخ", callback_data=f"support_reply:{msg['user_id']}:{msg['timestamp']}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"support_delete:{msg['user_id']}:{msg['timestamp']}"),
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="support_admin")],
    ])
    
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
    
    context.user_data["waiting_support_reply_to"] = user_id
    context.user_data["support_reply_timestamp"] = timestamp
    # آیدی همین پیام رو ذخیره می‌کنیم تا بعد از دریافت پاسخ، به‌جای پیام
    # جدید، همینو ویرایش کنیم
    context.user_data["support_reply_prompt_chat_id"] = query.message.chat_id
    context.user_data["support_reply_prompt_message_id"] = query.message.message_id


async def send_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پاسخ به کاربر"""
    if not context.user_data.get("waiting_support_reply_to"):
        return False
    
    user_id = context.user_data["waiting_support_reply_to"]
    reply_text = update.effective_message.text

    prompt_chat_id = context.user_data.pop("support_reply_prompt_chat_id", None)
    prompt_message_id = context.user_data.pop("support_reply_prompt_message_id", None)
    context.user_data.pop("support_reply_timestamp", None)
    context.user_data["waiting_support_reply_to"] = None

    try:
        await update.effective_message.delete()
    except Exception:
        pass

    if reply_text == "/cancel":
        result_text = "✘ پاسخ لغو شد."
    else:
        try:
            await context.bot.send_message(
                user_id,
                f"📩 **پاسخ پشتیبانی**\n\n{reply_text}\n\n"
                "💡 برای ارسال پیام جدید، دکمه پشتیبانی را بزنید.",
                parse_mode="Markdown"
            )
            result_text = "✔ پاسخ با موفقیت ارسال شد."
        except Exception as e:
            result_text = f"✘ خطا در ارسال: {e}"

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="support_admin")]])
    if prompt_chat_id and prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=prompt_chat_id, message_id=prompt_message_id,
                text=result_text, reply_markup=kb, parse_mode="Markdown"
            )
            return True
        except Exception:
            pass
    await context.bot.send_message(update.effective_chat.id, result_text, reply_markup=kb, parse_mode="Markdown")
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
