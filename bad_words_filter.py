# -*- coding: utf-8 -*-
"""
فیلتر فحش و سیستم اخطار خودکار:
اخطار ۱، اخطار ۲، اخطار ۳ -> دفعه ۴: سکوت ۵ دقیقه -> دفعه ۵: سکوت ۱۰ دقیقه -> دفعه ۶: بن کامل
"""

import time
import re
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

import database as db
from config import MUTE_DURATIONS_MIN
from persian_date import build_restriction_message
from permissions import get_permission_level


def normalize(text: str) -> str:
    """حذف فاصله و کاراکترهای زائد بین حروف برای تشخیص فحش‌های فاصله‌دار مثل «ک و ن ی»"""
    return re.sub(r"[\s\.\-_\*]+", "", text)


def contains_bad_word(text: str, bad_words) -> str | None:
    if not text:
        return None
    norm_text = normalize(text)
    lower_text = text.lower()
    for word in bad_words:
        if not word:
            continue
        if word in text or word in lower_text:
            return word
        if normalize(word) in norm_text:
            return word
    return None


async def _delete_message_later(context: ContextTypes.DEFAULT_TYPE):
    """تابع کمکی برای پاک کردن خودکار یک پیام بعد از مدت زمان مشخص"""
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass


async def check_message_for_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """این تابع روی هر پیام متنی گروه اجرا می‌شود (باید در main.py رجیستر شود)"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or chat.type not in ("group", "supergroup"):
        return
    if not user or user.is_bot:
        return

    group = db.get_group(chat.id)
    if group and not group["is_active"]:
        return

    # مدیران و مالک از فیلتر فحش معاف هستند
    level = await get_permission_level(context.bot, chat.id, user.id)
    if level in ("creator", "group_owner", "admin"):
        return

    text = message.text or message.caption or ""
    bad_words = db.get_bad_words(chat.id)
    matched = contains_bad_word(text, bad_words)
    if not matched:
        return

    # پاک کردن پیام فحش‌دار
    try:
        await message.delete()
    except Exception:
        pass

    username = f"@{user.username}" if user.username else user.full_name

    current_count = db.get_active_warning_count(chat.id, user.id)
    new_level = current_count + 1

    db.add_warning(chat.id, user.id, username, f"استفاده از کلمه نامناسب: {matched}", new_level)

    if new_level <= 3:
        wt = db.get_warning_text(chat.id, new_level)
        text_out = wt["text"] if wt and wt["text"] else f"اخطار {new_level}/3"
        warning_msg = await context.bot.send_message(
            chat.id,
            f"⚠️ {username}\n{text_out}",
            reply_to_message_id=None,
        )
        # این پیام اخطار بعد از ۱ دقیقه خودکار پاک می‌شود تا گروه شلوغ نشود
        context.job_queue.run_once(
            _delete_message_later, when=60,
            data={"chat_id": chat.id, "message_id": warning_msg.message_id},
            name=f"delwarn_{chat.id}_{warning_msg.message_id}"
        )
        if wt and wt["sticker_file_id"]:
            try:
                await context.bot.send_sticker(chat.id, wt["sticker_file_id"])
            except Exception:
                pass
        if wt and wt["gif_file_id"]:
            try:
                await context.bot.send_animation(chat.id, wt["gif_file_id"])
            except Exception:
                pass

    elif new_level in (4, 5):
        minutes = MUTE_DURATIONS_MIN[new_level]
        until_dt = datetime.now() + timedelta(minutes=minutes)
        until_ts = time.time() + minutes * 60
        try:
            await context.bot.restrict_chat_member(
                chat.id, user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_dt,
            )
        except Exception:
            pass
        db.add_mute(chat.id, user.id, username, "تکرار استفاده از الفاظ نامناسب (اخطار خودکار)", True, until_ts)
        which = "اول" if new_level == 4 else "دوم"
        mute_msg = await context.bot.send_message(
            chat.id,
            f"🔇 {username}\n"
            f"به دلیل تکرار بی‌ادبی، سکوت {which} فعال شد.\n"
            f"{build_restriction_message(until_dt, chat.title)}"
        )
        # این پیام تا زمانی که خودِ سکوت تموم بشه می‌مونه، بعدش خودکار پاک می‌شه
        context.job_queue.run_once(
            _delete_message_later, when=minutes * 60,
            data={"chat_id": chat.id, "message_id": mute_msg.message_id},
            name=f"delmute_{chat.id}_{mute_msg.message_id}"
        )

    else:  # new_level >= 6
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
        except Exception:
            pass
        db.add_ban(chat.id, user.id, username, "تکرار سه‌باره بی‌ادبی پس از اخطار و سکوت", True)
        await context.bot.send_message(
            chat.id,
            f"⛔️ {username}\nبه دلیل تکرار سه‌باره بی‌ادبی، به‌صورت کامل از گروه بن شد."
        )
