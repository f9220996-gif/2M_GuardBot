# -*- coding: utf-8 -*-
"""
ویرایش اخطارها (متن، استیکر، گیف، عکس)
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import can_access_dm_panel


def _warnedit_panel_content(chat_id):
    text = (
        "✏️ ویرایش اخطارها\n\n"
        "برای هر سطح اخطار، می‌توانید متن، استیکر، گیف یا عکس تنظیم کنید.\n\n"
        "سطح ۱ تا ۳: اخطار\n"
        "سطح ۴: سکوت ۵ دقیقه\n"
        "سطح ۵: سکوت ۱۰ دقیقه\n"
        "سطح ۶: بن کامل\n\n"
        "روی هر دکمه کلیک کنید تا آن سطح را ویرایش کنید:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ ۱", callback_data=f"warnedit_lvl:{chat_id}:1"),
            InlineKeyboardButton("⚠️ ۲", callback_data=f"warnedit_lvl:{chat_id}:2"),
            InlineKeyboardButton("⚠️ ۳", callback_data=f"warnedit_lvl:{chat_id}:3"),
        ],
        [
            InlineKeyboardButton("🔇 سکوت ۵ دقیقه", callback_data=f"warnedit_lvl:{chat_id}:4"),
            InlineKeyboardButton("🔇 سکوت ۱۰ دقیقه", callback_data=f"warnedit_lvl:{chat_id}:5"),
        ],
        [InlineKeyboardButton("⛔️ بن", callback_data=f"warnedit_lvl:{chat_id}:6")],
        [InlineKeyboardButton("🔄 بازنشانی همه", callback_data=f"warnedit_reset:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")],
    ])
    return text, kb


async def open_warnedit_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل اصلی ویرایش اخطارها"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    text, kb = _warnedit_panel_content(chat_id)
    await query.edit_message_text(text, reply_markup=kb)


def _level_panel_content(chat_id, level):
    wt = db.get_warning_text(chat_id, level)

    text = f"✏️ ویرایش اخطار سطح {level}\n\n"
    if wt:
        text += f"📝 متن فعلی: {wt['text'] if wt['text'] else 'تعیین نشده'}\n"
        text += f"🎬 استیکر: {'✔' if wt['sticker_file_id'] else '✘'}\n"
        text += f"🎞 گیف: {'✔' if wt['gif_file_id'] else '✘'}\n"
        text += f"🖼 عکس: {'✔' if wt['photo_file_id'] else '✘'}\n\n"
    else:
        text += "📝 متن فعلی: تعیین نشده\n"
        text += "🎬 استیکر: ✘\n"
        text += "🎞 گیف: ✘\n"
        text += "🖼 عکس: ✘\n\n"
    text += "برای ویرایش، روی دکمه‌های زیر کلیک کنید:"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ویرایش متن", callback_data=f"warnedit_text:{chat_id}:{level}")],
        [InlineKeyboardButton("🎬 افزودن استیکر", callback_data=f"warnedit_media:{chat_id}:{level}:sticker")],
        [InlineKeyboardButton("🎞 افزودن گیف", callback_data=f"warnedit_media:{chat_id}:{level}:gif")],
        [InlineKeyboardButton("🖼 افزودن عکس", callback_data=f"warnedit_media:{chat_id}:{level}:photo")],
        [InlineKeyboardButton("🗑 پاک کردن مدیا", callback_data=f"warnedit_media:{chat_id}:{level}:clear")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"warnedit_panel:{chat_id}")],
    ])
    return text, kb


async def open_level_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل ویرایش یک سطح خاص"""
    query = update.callback_query
    await query.answer()
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    text, kb = _level_panel_content(chat_id, level)
    await query.edit_message_text(text, reply_markup=kb)


async def ask_warn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست متن جدید برای اخطار"""
    query = update.callback_query
    await query.answer()
    _, chat_id, level = query.data.split(":")
    chat_id, level = int(chat_id), int(level)

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    context.user_data["waiting_for_warn_text"] = (chat_id, level)
    context.user_data["warnedit_prompt_chat_id"] = query.message.chat_id
    context.user_data["warnedit_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"warnedit_lvl:{chat_id}:{level}")]
    ])
    await query.edit_message_text(
        f"📝 ویرایش متن اخطار سطح {level}\n\n"
        "لطفاً متن جدید را ارسال کنید.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb
    )


async def _return_to_level_panel(update, context, chat_id, level):
    """پیام تایپ‌شده رو پاک می‌کنه و پیام «لطفاً بفرست» رو ویرایش می‌کنه به پنل سطح"""
    prompt_chat_id = context.user_data.pop("warnedit_prompt_chat_id", None)
    prompt_message_id = context.user_data.pop("warnedit_prompt_message_id", None)

    try:
        await update.effective_message.delete()
    except Exception:
        pass

    text, kb = _level_panel_content(chat_id, level)
    if prompt_chat_id and prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=prompt_chat_id, message_id=prompt_message_id,
                text=text, reply_markup=kb
            )
            return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb)


async def receive_warn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید اخطار"""
    if not context.user_data.get("waiting_for_warn_text"):
        return False

    chat_id, level = context.user_data["waiting_for_warn_text"]
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        return False

    text = update.effective_message.text
    context.user_data["waiting_for_warn_text"] = None

    if text == "/cancel":
        await _return_to_level_panel(update, context, chat_id, level)
        return True

    db.set_warning_text(chat_id, level, text=text)
    await _return_to_level_panel(update, context, chat_id, level)
    return True


async def ask_warn_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست مدیا برای اخطار"""
    query = update.callback_query
    await query.answer()
    _, chat_id, level, media_type = query.data.split(":")
    chat_id, level = int(chat_id), int(level)

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    if media_type == "clear":
        db.set_warning_text(chat_id, level, text=None)
        await query.answer("✔ مدیا پاک شد")
        await open_level_panel(update, context)
        return

    media_names = {
        "sticker": "استیکر",
        "gif": "گیف",
        "photo": "عکس"
    }

    context.user_data["waiting_for_warn_media"] = (chat_id, level, media_type)
    context.user_data["warnedit_prompt_chat_id"] = query.message.chat_id
    context.user_data["warnedit_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"warnedit_lvl:{chat_id}:{level}")]
    ])
    await query.edit_message_text(
        f"🎬 افزودن {media_names.get(media_type, 'مدیا')} به اخطار سطح {level}\n\n"
        f"لطفاً یک {media_names.get(media_type, 'مدیا')} ارسال کنید.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb
    )


async def receive_warn_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مدیا برای اخطار"""
    if not context.user_data.get("waiting_for_warn_media"):
        return False

    chat_id, level, media_type = context.user_data["waiting_for_warn_media"]
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        return False

    message = update.effective_message

    if message.text == "/cancel":
        context.user_data["waiting_for_warn_media"] = None
        await _return_to_level_panel(update, context, chat_id, level)
        return True

    file_id = None
    if media_type == "sticker" and message.sticker:
        file_id = message.sticker.file_id
    elif media_type == "gif" and message.animation:
        file_id = message.animation.file_id
    elif media_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    else:
        try:
            await message.delete()
        except Exception:
            pass
        warn = await message.reply_text("❌ نوع مدیا اشتباه است. لطفاً دوباره ارسال کنید یا /cancel رو بفرستید.")
        return True

    if media_type == "sticker":
        db.set_warning_text(chat_id, level, sticker_file_id=file_id)
    elif media_type == "gif":
        db.set_warning_text(chat_id, level, gif_file_id=file_id)
    elif media_type == "photo":
        db.set_warning_text(chat_id, level, photo_file_id=file_id)

    context.user_data["waiting_for_warn_media"] = None
    await _return_to_level_panel(update, context, chat_id, level)
    return True


async def reset_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازنشانی اخطارها به حالت پیش‌فرض"""
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    for level in range(1, 7):
        db.reset_warning_text(chat_id, level)

    await query.answer("✔ بازنشانی شد")
    await open_warnedit_panel(update, context)
