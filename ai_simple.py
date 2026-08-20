import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import ContextTypes

# کلید از محیط متغیر
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash-lite")

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به پیام‌هایی که ربات تگ شده"""
    
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    bot_username = context.bot.username
    
    # فقط اگه ربات تگ شده بود
    if f"@{bot_username}" not in text:
        return
    
    # پاک کردن تگ از متن
    question = re.sub(f"@{bot_username}", "", text).strip()
    
    if not question:
        await update.message.reply_text("🧐 چی بپرسم؟")
        return
    
    # پیام در حال فکر کردن
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    try:
        # سوال از Gemini
        response = model.generate_content(question)
        reply = response.text
        
        # اگه طولانی بود، کوتاه کن
        if len(reply) > 4000:
            reply = reply[:4000] + "..."
        
    except Exception as e:
        reply = f"❌ خطا: {str(e)}"
    
    # پاک کردن پیام "در حال فکر کردن"
    await thinking.delete()
    
    # ارسال پاسخ
    await update.message.reply_text(reply)
