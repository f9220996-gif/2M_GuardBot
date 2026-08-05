# -*- coding: utf-8 -*-
"""
خوش‌آمدگویی خودکار به عضو جدید گروه، با متن قابل‌تنظیم و جای‌گذاری خودکار.
جای‌گذاری‌های پشتیبانی‌شده در متن: {user}  {group}  {date}  {time}
"""

from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from persian_date import format_persian_date_only, format_persian_time_only
from permissions import is_creator, is_group_owner

WAITING_WELCOME_TEXT_KEY = "waiting_welcome_text_chat_id"
WAITING_WELCOME_MEDIA_KEY = "waiting_welcome_media_chat_id"


def render_welcome_text(template: str, user_name: str, group_title: str) -> str:
    now = datetime.now()
    return (
        template
        .replace("{user}", user_name)
        .replace("{group}", group_title or "")
        .replace("{date}", format_persian_date_only(now))
        .replace("{time}", format_persian_time_only(now))
    )


async def on_new_member_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام خوش‌آمد برای اعضای تازه‌وارد (غیر از خودِ ربات)"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.new_chat_members:
        return

    me = await context.bot.get_me()
    real_members = [m for m in message.new_chat_members if m.id != me.id]
    if not real_members:
        return  # این خودِ ربات بود، جای دیگه‌ای مدیریت می‌شه

    if not db.is_feature_enabled(chat.id, "welcome"):
        return

    template = db.get_welcome_text(chat.id)
    sticker_id, animation_id = db.get_welcome_media(chat.id)
    for member in real_members:
        user_name = f"@{member.username}" if member.username else member.full_name
        text = render_welcome_text(template, user_name, chat.title)
        try:
            if animation_id:
                await context.bot.send_animation(chat.id, animation_id, caption=text)
            elif sticker_id:
                await context.bot.send_sticker(chat.id, sticker_id)
                await context.bot.send_message(chat.id, text)
            else:
                await context.bot.send_message(chat.id, text)
        except Exception:
            pass


async def _user_can_manage(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


def _welcome_panel_keyboard(chat_id):
    enabled = db.is_feature_enabled(chat_id, "welcome")
    toggle = (
        InlineKeyboardButton("❌ خاموش کردن خوش‌آمدگویی", callback_data=f"wc_off:{chat_id}")
        if enabled else
        InlineKeyboardButton("✅ روشن کردن خوش‌آمدگویی", callback_data=f"wc_on:{chat_id}")
    )
    sticker_id, animation_id = db.get_welcome_media(chat_id)
    media_row = (
        [InlineKeyboardButton("🗑 حذف گیف/استیکر", callback_data=f"wc_media_clear:{chat_id}")]
        if (sticker_id or animation_id) else
        [InlineKeyboardButton("🖼 افزودن گیف/استیکر", callback_data=f"wc_media:{chat_id}")]
    )
    return InlineKeyboardMarkup([
        [toggle],
        [InlineKeyboardButton("✏️ نوشتن متن دلخواه", callback_data=f"wc_edit:{chat_id}")],
        media_row,
        [InlineKeyboardButton("👁 دیدن متن فعلی", callback_data=f"wc_preview:{chat_id}")],
        [InlineKeyboardButton("↩️ برگردوندن به پیش‌فرض", callback_data=f"wc_reset:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])


async def open_welcome_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    status = "✅ فعال" if db.is_feature_enabled(chat_id, "welcome") else "❌ غیرفعال"
    text = (
        "👋 تنظیمات خوش‌آمدگویی\n\n"
        f"وضعیت: {status}\n\n"
        "می‌تونی متن دلخواه بنویسی و از این کلمات استفاده کنی:\n"
        "{user} = اسم عضو جدید\n"
        "{group} = اسم گروه\n"
        "{date} = تاریخ\n"
        "{time} = ساعت"
    )
    await query.edit_message_text(text, reply_markup=_welcome_panel_keyboard(chat_id))


async def toggle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, chat_id = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_feature_enabled(chat_id, "welcome", action == "wc_on")
    await query.answer("ذخیره شد ✅")
    await open_welcome_panel(update, context)


async def preview_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    template = db.get_welcome_text(chat_id)
    group = db.get_group(chat_id)
    group_title = group["title"] if group else ""
    sample = render_welcome_text(template, "@نمونه_کاربر", group_title)
    sticker_id, animation_id = db.get_welcome_media(chat_id)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"wc_panel:{chat_id}")]])
    if animation_id:
        try:
            await context.bot.send_animation(chat_id=user.id, animation=animation_id, caption=sample)
        except Exception:
            pass
    elif sticker_id:
        try:
            await context.bot.send_sticker(chat_id=user.id, sticker=sticker_id)
        except Exception:
            pass
    await query.edit_message_text(f"👁 نمونه‌ی پیام خوش‌آمد:\n\n{sample}", reply_markup=kb)


async def reset_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.reset_welcome_text(chat_id)
    await query.answer("به پیش‌فرض برگشت ✅")
    await open_welcome_panel(update, context)


async def ask_edit_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data[WAITING_WELCOME_TEXT_KEY] = chat_id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"wc_panel:{chat_id}")]])
    await query.edit_message_text(
        "✏️ متن جدید خوش‌آمدگویی رو همینجا بفرست.\n\n"
        "می‌تونی از {user}، {group}، {date}، {time} استفاده کنی.",
        reply_markup=kb
    )


async def receive_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگر منتظر متن خوش‌آمد بودیم، همین‌جا ذخیره‌ش می‌کنیم. True یعنی پیام مصرف شد."""
    chat_id = context.user_data.get(WAITING_WELCOME_TEXT_KEY)
    if not chat_id:
        return False

    user = update.effective_user
    if not await _user_can_manage(context.bot, user.id, chat_id):
        return False

    context.user_data[WAITING_WELCOME_TEXT_KEY] = None
    new_text = update.effective_message.text
    db.set_welcome_text(chat_id, new_text)
    await update.effective_message.reply_text(f"✅ متن خوش‌آمدگویی ذخیره شد:\n\n{new_text}")
    return True


async def ask_add_welcome_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data[WAITING_WELCOME_MEDIA_KEY] = chat_id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"wc_panel:{chat_id}")]])
    await query.edit_message_text(
        "🖼 یک گیف یا استیکر همینجا برام بفرست تا برای خوش‌آمدگویی ذخیره بشه.",
        reply_markup=kb
    )


async def receive_welcome_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگر منتظر گیف/استیکر خوش‌آمد بودیم، همین‌جا ذخیره‌ش می‌کنیم. True یعنی پیام مصرف شد."""
    chat_id = context.user_data.get(WAITING_WELCOME_MEDIA_KEY)
    if not chat_id:
        return False

    user = update.effective_user
    if not await _user_can_manage(context.bot, user.id, chat_id):
        return False

    message = update.effective_message
    if message.sticker:
        db.set_welcome_media(chat_id, sticker_file_id=message.sticker.file_id)
    elif message.animation:
        db.set_welcome_media(chat_id, animation_file_id=message.animation.file_id)
    else:
        await message.reply_text("❗️ این گیف یا استیکر نبود. لطفاً یه گیف یا استیکر بفرست.")
        return True

    context.user_data[WAITING_WELCOME_MEDIA_KEY] = None
    await message.reply_text("✅ ذخیره شد.")
    return True


async def clear_welcome_media_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.clear_welcome_media(chat_id)
    await query.answer("حذف شد ✅")
    await open_welcome_panel(update, context)
