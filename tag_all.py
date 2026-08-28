# -*- coding: utf-8 -*-
"""
تگ کردن اعضایی که قبلاً در گروه پیام داده‌اند (با کلمه "تگ")

توجه: تلگرام به هیچ رباتی اجازه نمی‌دهد لیست کامل اعضای یک گروه را بگیرد،
برای همین به‌جای آن، هر کاربری که پیام می‌دهد در دیتابیس ثبت می‌شود و
دستور «تگ» همان لیست ثبت‌شده را منشن می‌کند.
"""

import time
import asyncio
from html import escape

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from permissions import is_admin
import database as db


async def track_seen_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """روی هر پیام گروه اجرا می‌شود تا فرستنده‌اش در دیتابیس ثبت شود"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or chat.type not in ("group", "supergroup"):
        return
    if user.is_bot:
        return

    db.save_seen_user(chat.id, user.id, user.username, user.full_name)


async def tag_all_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تگ کردن اعضایی که قبلاً در گروه پیام داده‌اند، با کلمه "تگ" """

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or chat.type not in ("group", "supergroup"):
        return

    # ===== چک کردن کلمه "تگ" =====
    text = (message.text or "").strip()
    if text != "تگ":
        return
    # ==============================

    # ===== فقط مدیران =====
    if not await is_admin(context.bot, chat.id, user.id):
        await message.reply_text("⛔️ فقط مدیران گروه می‌توانند از این دستور استفاده کنند.")
        return
    # =======================

    # ===== جلوگیری از اسپم (هر ۵ دقیقه یکبار) =====
    last_use = context.chat_data.get("tag_all_last_use", 0)
    if time.time() - last_use < 300:
        remaining = int(300 - (time.time() - last_use))
        await message.reply_text(f"⏳ لطفاً {remaining} ثانیه صبر کنید.")
        return
    # =============================================

    context.chat_data["tag_all_last_use"] = time.time()

    # ===== پیام در حال اجرا =====
    status_msg = await message.reply_text("🔄 در حال تگ کردن اعضا...")
    # =============================

    try:
        # ===== دریافت لیست مدیران (برای حذف‌شون از تگ) =====
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_ids = [admin.user.id for admin in admins]
        # =====================================================

        # ===== دریافت کاربرانی که قبلاً پیام داده‌اند (از دیتابیس) =====
        rows = db.get_seen_users(chat.id)
        members = [
            {"id": r["user_id"], "username": r["username"], "full_name": r["full_name"]}
            for r in rows
        ]
        # ================================================================

        if not members:
            await status_msg.edit_text(
                "❌ هنوز کسی رو تو این گروه ثبت نکردم. اول باید چند نفر پیام بدن."
            )
            return

        # ===== ساخت لیست تگ (با HTML امن، نه Markdown) =====
        mentions = []
        for member in members:
            if member["id"] in admin_ids:  # مدیران رو تگ نکن
                continue
            if member["username"]:
                mentions.append(f"@{escape(member['username'])}")
            else:
                safe_name = escape(member["full_name"] or "کاربر")
                mentions.append(f'<a href="tg://user?id={member["id"]}">{safe_name}</a>')
        # ====================================================

        if not mentions:
            await status_msg.edit_text("❌ هیچ کاربری برای تگ کردن وجود ندارد.")
            return

        # ===== تقسیم به گروه‌های ۵۰ تایی =====
        chunk_size = 50
        chunks = [mentions[i:i + chunk_size] for i in range(0, len(mentions), chunk_size)]
        # ====================================

        # ===== حذف پیام "در حال اجرا" =====
        await status_msg.delete()
        # ==================================

        # ===== ارسال پیام‌های تگ =====
        for i, chunk in enumerate(chunks):
            text_msg = f"🔔 <b>تگ</b> (بخش {i + 1}/{len(chunks)})\n\n"
            text_msg += " ".join(chunk)

            if i == 0:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ بستن", callback_data=f"tag_close:{chat.id}")]
                ])
                await message.reply_text(text_msg, parse_mode="HTML", reply_markup=kb)
            else:
                await message.reply_text(text_msg, parse_mode="HTML")

            await asyncio.sleep(1)
        # ==================================

    except Exception as e:
        await status_msg.edit_text(f"❌ خطا: {str(e)}")


async def tag_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بستن پیام تگ"""
    query = update.callback_query
    await query.answer()

    try:
        await query.message.delete()
    except Exception:
        pass
