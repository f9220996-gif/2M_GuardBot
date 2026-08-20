import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import ContextTypes

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("⚠️ GOOGLE_API_KEY تنظیم نشده!")

# ===== مدل جدید gemini-3.6-flash =====
model = genai.GenerativeModel("gemini-3.6-flash")
# =====================================

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    bot_username = context.bot.username
    
    if "@Bot" not in text and f"@{bot_username}" not in text:
        return
    
    question = re.sub(r"@Bot\s*", "", text)
    question = re.sub(f"@{bot_username}\s*", "", question)
    question = question.strip()
    
    if not question:
        await update.message.reply_text("🧐 چی بپرسم؟")
        return
    
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    try:
        response = model.generate_content(question)
        reply = response.text
        if len(reply) > 4000:
            reply = reply[:4000] + "..."
        await thinking.delete()
        await update.message.reply_text(reply)
    except Exception as e:
        await thinking.delete()
        await update.message.reply_text(f"❌ خطا: {str(e)}")
