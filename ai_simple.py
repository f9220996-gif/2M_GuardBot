import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import ContextTypes

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    bot_username = context.bot.username
    
    # فقط اگه ربات تگ شده بود (با @Bot یا اسم کامل)
    if "@Bot" not in text and f"@{bot_username}" not in text:
        return
    
    # پاک کردن تگ
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
    except Exception as e:
        reply = f"❌ خطا: {str(e)}"
    
    await thinking.delete()
    await update.message.reply_text(reply)
