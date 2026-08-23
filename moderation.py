# -*- coding: utf-8 -*-
"""
دستورات مدیریتی گروه:
خاموشی / روشن / سکوت / آزاد کن / بن کن / پاک / گیف بن / استیکر بن
"""

import time
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

import database as db
from permissions import can_use_moderation_commands, can_target_user, parse_duration_seconds, get_permission_level
from persian_date import build_restriction_message, build_duration_text, utc_from_ts, tehran_from_ts


async def _require_group(update: Update):
    chat = update.effective_chat
    return chat and chat.type in ("group", "supergroup")


async def _reply(update, text):
    await update.effective_message.reply_text(text)


# ---------------------------------------------------------------------------
# خاموشی [Xh/Xm/Xs]  -> قفل کردن گروه (فقط مدیران بتوانند پیام بدهند)
# ---------------------------------------------------------------------------

async def cmd_khamoshi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند گروه را خاموش کنند.")
        return

    args_text = " ".join(context.args) if context.args else ""
    duration = parse_duration_seconds(args_text)

    try:
        await context.bot.set_chat_permissions(
            chat.id,
            ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        await _reply(update, f"✘ نتونستم گروه رو قفل کنم. مطمئن شو ربات ادمینه.\n{e}")
        return

    if duration:
        until_ts = time.time() + duration
        db.set_group_lock(chat.id, True, until_ts)
        until_dt_display = tehran_from_ts(until_ts)
        job_name = f"unlock_{chat.id}"
        context.job_queue.run_once(
            _auto_unlock_job, when=duration, chat_id=chat.id, name=job_name, data={"chat_id": chat.id}
        )
        await _reply(
            update,
            f"🔒 گروه قفل شد.\n"
            f"⏳ به‌صورت خودکار بعد از {build_duration_text(duration)} باز می‌شود "
            f"(حدود {until_dt_display.strftime('%H:%M')})."
        )
    else:
        db.set_group_lock(chat.id, True, None)
        await _reply(update, "🔒 گروه قفل شد (فقط مدیران می‌توانند پیام بدهند).")


async def _auto_unlock_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    group = db.get_group(chat_id)
    if not group or not group["is_locked"]:
        return
    try:
        await context.bot.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
    except Exception:
        pass
    db.set_group_lock(chat_id, False, None)
    try:
        await context.bot.send_message(chat_id, "🔓 گروه به‌صورت خودکار باز شد.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# روشن -> باز کردن فوری گروه حتی اگه تایمر داشته
# ---------------------------------------------------------------------------

async def cmd_roshan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند گروه را باز کنند.")
        return

    try:
        await context.bot.set_chat_permissions(
            chat.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
    except Exception as e:
        await _reply(update, f"❌ نتونستم گروه رو باز کنم.\n{e}")
        return

    # لغو تایمر خودکار در صورت وجود
    for job in context.job_queue.get_jobs_by_name(f"unlock_{chat.id}"):
        job.schedule_removal()

    db.set_group_lock(chat.id, False, None)
    await _reply(update, "🔓 گروه باز شد.")


# ---------------------------------------------------------------------------
# سکوت [مدت]  (باید ریپلای روی پیام کاربر باشد)
# ---------------------------------------------------------------------------

async def cmd_sokoot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند کاربر را سکوت بدهند.")
        return

    if not message.reply_to_message:
        await _reply(update, "❗️ لطفاً روی پیام کاربر مورد نظر ریپلای کن و بنویس: سکوت 30m")
        return

    target = message.reply_to_message.from_user
    if not await can_target_user(context.bot, chat.id, user.id, target.id):
        await _reply(update, "⛔️ شما اجازه سکوت دادن به این کاربر را ندارید.")
        return

    args_text = " ".join(context.args) if context.args else ""
    duration = parse_duration_seconds(args_text)
    reason = None
    if args_text:
        # هرچی بعد از عدد/واحد زمانی باقی موند به عنوان دلیل در نظر گرفته میشه
        import re
        reason_text = re.sub(r"(\d+)\s*(h|m|s|ساعت|دقیقه|ثانیه)", "", args_text, flags=re.IGNORECASE).strip()
        reason = reason_text or None

    if not duration:
        duration = 10 * 60  # پیش‌فرض ۱۰ دقیقه اگر عددی داده نشده

    until_ts = time.time() + duration
    until_dt_api = utc_from_ts(until_ts)
    until_dt_display = tehran_from_ts(until_ts)

    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_dt_api,
        )
    except Exception as e:
        await _reply(update, f"❌ نتونستم کاربر رو سکوت بدم.\n{e}")
        return

    username = f"@{target.username}" if target.username else target.full_name
    db.add_mute(chat.id, target.id, username, reason, bool(reason), until_ts)

    await _reply(
        update,
        f"🔇 {username} به مدت {build_duration_text(duration)} سکوت شد.\n"
        f"{build_restriction_message(until_dt_display, chat.title)}"
        + (f"\nدلیل: {reason}" if reason else "")
    )


# ---------------------------------------------------------------------------
# آزاد کن (ریپلای) -> برداشتن سکوت
# ---------------------------------------------------------------------------

async def cmd_azad_kon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند سکوت را بردارند.")
        return

    if not message.reply_to_message:
        await _reply(update, "❗️ لطفاً روی پیام کاربر مورد نظر ریپلای کن و بنویس: آزاد کن")
        return

    target = message.reply_to_message.from_user

    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
    except Exception as e:
        await _reply(update, f"❌ نتونستم سکوت رو بردارم.\n{e}")
        return

    db.remove_mute(chat.id, target.id)
    username = f"@{target.username}" if target.username else target.full_name
    sent_msg = await update.effective_message.reply_text(f"🔊 سکوت {username} برداشته شد.")
    context.job_queue.run_once(
        _delete_message_later, when=5,
        data={"chat_id": chat.id, "message_id": sent_msg.message_id},
        name=f"delazad_{chat.id}_{sent_msg.message_id}"
    )


# ---------------------------------------------------------------------------
# بن کن (ریپلای) -> بن کامل کاربر
# ---------------------------------------------------------------------------

async def cmd_ban_kon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند کاربر را بن کنند.")
        return

    if not message.reply_to_message:
        await _reply(update, "❗️ لطفاً روی پیام کاربر مورد نظر ریپلای کن و بنویس: بن کن [دلیل اختیاری]")
        return

    target = message.reply_to_message.from_user
    if not await can_target_user(context.bot, chat.id, user.id, target.id):
        await _reply(update, "⛔️ شما اجازه بن کردن این کاربر را ندارید.")
        return

    reason = " ".join(context.args) if context.args else None

    try:
        await context.bot.ban_chat_member(chat.id, target.id)
    except Exception as e:
        await _reply(update, f"❌ نتونستم کاربر رو بن کنم.\n{e}")
        return

    username = f"@{target.username}" if target.username else target.full_name
    db.add_ban(chat.id, target.id, username, reason, bool(reason))

    await _reply(
        update,
        f"⛔️ {username} از گروه بن شد."
        + (f"\nدلیل: {reason}" if reason else "\n(بدون دلیل ثبت‌شده)")
    )


# ---------------------------------------------------------------------------
# پاک (ریپلای) -> حذف پیام
# ---------------------------------------------------------------------------

async def _delete_message_later(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass


async def cmd_pak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند پیام پاک کنند.")
        return

    if not message.reply_to_message:
        await _reply(update, "❗️ لطفاً روی پیام مورد نظر ریپلای کن و بنویس: پاک")
        return

    # پیامی که روش ریپلای شده (متن، عکس، هرچی) سریع پاک می‌شود
    try:
        await message.reply_to_message.delete()
    except Exception as e:
        await _reply(update, f"❌ نتونستم اون پیام رو پاک کنم.\n{e}")
        return

    # پیام خودِ دستور «پاک» با ۲ ثانیه تاخیر پاک می‌شود
    context.job_queue.run_once(
        _delete_message_later, when=2,
        data={"chat_id": chat.id, "message_id": message.message_id},
        name=f"delcmd_{chat.id}_{message.message_id}"
    )


# ---------------------------------------------------------------------------
# گیف بن / استیکر بن (ریپلای روی گیف یا استیکر)
# ---------------------------------------------------------------------------

async def cmd_gif_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند گیف بن کنند.")
        return

    target_msg = message.reply_to_message
    if not target_msg or not target_msg.animation:
        await _reply(update, "❗️ لطفاً روی یک گیف ریپلای کن و بنویس: گیف بن")
        return

    db.add_blacklist_gif(chat.id, target_msg.animation.file_unique_id)
    try:
        await target_msg.delete()
    except Exception:
        pass
    await _reply(update, "🚫 این گیف به لیست سیاه اضافه شد و از این به بعد در گروه حذف می‌شود.")


async def cmd_sticker_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _require_group(update):
        return
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not await can_use_moderation_commands(context.bot, chat.id, user.id):
        await _reply(update, "⛔️ فقط مدیران، مالک گروه یا سازنده ربات می‌توانند استیکر بن کنند.")
        return

    target_msg = message.reply_to_message
    if not target_msg or not target_msg.sticker:
        await _reply(update, "❗️ لطفاً روی یک استیکر ریپلای کن و بنویس: استیکر بن")
        return

    db.add_blacklist_sticker(chat.id, target_msg.sticker.file_unique_id)
    try:
        await target_msg.delete()
    except Exception:
        pass
    await _reply(update, "🚫 این استیکر به لیست سیاه اضافه شد و از این به بعد در گروه حذف می‌شود.")


# ---------------------------------------------------------------------------
# چک خودکار گیف/استیکر بلک‌لیست‌شده روی هر پیام مدیا
# ---------------------------------------------------------------------------

async def check_media_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اگه ارسال عکس/فیلم/فایل برای این گروه از پنل خاموش شده باشه، پیام رو پاک می‌کنه
    و به فرستنده (اگه مدیر/مالک/سازنده نباشه) با یه پیام کوتاه اطلاع می‌ده.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return
    if not user or user.is_bot:
        return

    level = await get_permission_level(context.bot, chat.id, user.id)
    if level in ("creator", "group_owner", "admin"):
        return  # مدیران و مالک همیشه مجازن

    checks = [
        (message.photo, "photos", "عکس"),
        (message.video, "videos", "فیلم"),
        (message.document, "documents", "فایل"),
    ]
    for present, key, label in checks:
        if present and not db.is_feature_enabled(chat.id, key):
            try:
                await message.delete()
            except Exception:
                pass
            uname = f"@{user.username}" if user.username else user.full_name
            try:
                warn_msg = await context.bot.send_message(
                    chat.id, f"🚫 {uname} شما اجازه ارسال {label} رو ندارید."
                )
                context.job_queue.run_once(
                    _delete_message_later, when=5,
                    data={"chat_id": chat.id, "message_id": warn_msg.message_id},
                    name=f"delmedia_{chat.id}_{warn_msg.message_id}"
                )
            except Exception:
                pass
            return


async def check_blacklisted_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return
    if not db.is_feature_enabled(chat.id, "blacklist"):
        return

    if message.animation and db.is_gif_blacklisted(chat.id, message.animation.file_unique_id):
        user = update.effective_user
        uname = f"@{user.username}" if user and user.username else (user.full_name if user else "")
        try:
            await message.delete()
        except Exception:
            pass
        try:
            warn_msg = await context.bot.send_message(chat.id, f"🚫 {uname} این گیف تو این گروه مجاز نیست.")
            context.job_queue.run_once(
                _delete_message_later, when=5,
                data={"chat_id": chat.id, "message_id": warn_msg.message_id},
                name=f"delblk_{chat.id}_{warn_msg.message_id}"
            )
        except Exception:
            pass
        return

    if message.sticker and db.is_sticker_blacklisted(chat.id, message.sticker.file_unique_id):
        user = update.effective_user
        uname = f"@{user.username}" if user and user.username else (user.full_name if user else "")
        try:
            await message.delete()
        except Exception:
            pass
        try:
            warn_msg = await context.bot.send_message(chat.id, f"🚫 {uname} این استیکر تو این گروه مجاز نیست.")
            context.job_queue.run_once(
                _delete_message_later, when=5,
                data={"chat_id": chat.id, "message_id": warn_msg.message_id},
                name=f"delblk_{chat.id}_{warn_msg.message_id}"
            )
        except Exception:
            pass
        return
