import os
import re
import requests
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    print("⚠️ هشدار: DEEPSEEK_API_KEY تنظیم نشده!")

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    bot_username = context.bot.username
    
    if f"@{bot_username}" not in text:
        return
    
    question = re.sub(f"@{bot_username}", "", text).strip()
    
    if not question:
        await update.message.reply_text("🧐 چی بپرسم؟")
        return
    
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "تو یه دستیار مفید فارسی‌زبان هستی. پاسخ‌هات مختصر باشه."},
                {"role": "user", "content": question}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
        else:
            reply = f"❌ خطا: {response.status_code}"
    except Exception as e:
        reply = f"❌ خطا: {str(e)}"
    
    await thinking.delete()
    await update.message.reply_text(reply)
