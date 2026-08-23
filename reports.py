# -*- coding: utf-8 -*-
"""
دستور «گزارش»: هر عضو عادی می‌تونه با ریپلای روی پیام یه نفر بنویسه «گزارش».
همه‌ی گزارش‌های هر گروه هر ۲ دقیقه یک‌جا جمع و برای مالک همون گروه
(کسی که ربات رو اضافه کرده) به پی‌وی ارسال می‌شه، تا اسپم نشه.
"""

from telegram import Update
from telegram.ext import ContextTypes

import database as db


async def cmd_gozaresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not chat or chat.type not in ("group", "supergroup"):
        return

    if not message.reply_to_message:
        await message.reply_text("❗️ برای گزارش، روی پیام مورد نظر ریپلای کن و بنویس: گزارش")
        return

    reported = message.reply_to_message.from_user
    if not reported:
        return

    reporter_name = f"@{user.username}" if user.username else user.full_name
    reported_name = f"@{reported.username}" if reported.username else reported.full_name
    snippet = (message.reply_to_message.text or message.reply_to_message.caption or "[بدون متن / رسانه]")[:200]

    db.add_report(chat.id, user.id, reporter_name, reported.id, reported_name, snippet)

    try:
        await message.reply_text("✔ گزارش شما ثبت شد و به مالک گروه اطلاع داده می‌شود.")
    except Exception:
        pass


async def send_pending_reports_job(context: ContextTypes.DEFAULT_TYPE):
    """این تابع هر ۲ دقیقه یک‌بار توسط job_queue اجرا می‌شود"""
    for chat_id in db.get_chats_with_pending_reports():
        reports = db.get_pending_reports(chat_id)
        if not reports:
            continue

        group = db.get_group(chat_id)
        owner_id = group["added_by_user_id"] if group else None
        if not owner_id:
            db.mark_reports_sent(chat_id)  # مالکی نداره، فقط پاکش کن که تکرار نشه
            continue

        title = group["title"] if group and group["title"] else str(chat_id)
        lines = [f"🚨 گزارش‌های جدید گروه «{title}» ({len(reports)} مورد):\n"]
        for r in reports:
            lines.append(
                f"• {r['reporter_username']} گزارش داد از {r['reported_username']}\n"
                f"  متن: {r['message_snippet']}"
            )
        text = "\n\n".join(lines)

        try:
            await context.bot.send_message(owner_id, text[:4000])
            db.mark_reports_sent(chat_id)
        except Exception:
            pass  # اگه مالک پی‌وی ربات رو نبسته/استارت نکرده، دفعه بعد دوباره تلاش می‌شه
