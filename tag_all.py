# -*- coding: utf-8 -*-
"""
تگ کردن همه اعضای گروه با کلمه "تگ"
"""

import time
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from permissions import is_admin


async def tag_all_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تگ کردن همه اعضای گروه با کلمه "تگ" """
    
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
        # ===== دریافت لیست مدیران =====
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_ids = [admin.user.id for admin in admins]
        # ===============================
        
        # ===== دریافت اعضایی که اخیراً پیام دادن =====
        # از تاریخچه پیام‌های اخیر استفاده میکنیم
        members = []
        async for msg in context.bot.get_chat_history(chat.id, limit=100):
            if msg.from_user and not msg.from_user.is_bot:
                if msg.from_user.id not in [m["id"] for m in members]:
                    members.append({
                        "id": msg.from_user.id,
                        "username": msg.from_user.username,
                        "full_name": msg.from_user.full_name
                    })
        # =============================================
        
        if not members:
            await status_msg.edit_text("❌ هیچ کاربری برای تگ کردن وجود ندارد.")
            return
        
        # ===== ساخت لیست تگ =====
        mentions = []
        for member in members:
            if member["id"] not in admin_ids:  # مدیران رو تگ نکن
                if member["username"]:
                    mentions.append(f"@{member['username']}")
                else:
                    mentions.append(f"[{member['full_name']}](tg://user?id={member['id']})")
        # ========================
        
        if not mentions:
            await status_msg.edit_text("❌ هیچ کاربری برای تگ کردن وجود ندارد.")
            return
        
        # ===== تقسیم به گروه‌های ۵۰ تایی =====
        chunk_size = 50
        chunks = [mentions[i:i+chunk_size] for i in range(0, len(mentions), chunk_size)]
        # ====================================
        
        # ===== حذف پیام "در حال اجرا" =====
        await status_msg.delete()
        # ==================================
        
        # ===== ارسال پیام‌های تگ =====
        for i, chunk in enumerate(chunks):
            text_msg = f"🔔 **تگ** (بخش {i+1}/{len(chunks)})\n\n"
            text_msg += "\n".join(chunk)
            
            if i == 0:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ بستن", callback_data=f"tag_close:{chat.id}")]
                ])
                await message.reply_text(text_msg, parse_mode="Markdown", reply_markup=kb)
            else:
                await message.reply_text(text_msg, parse_mode="Markdown")
            
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
