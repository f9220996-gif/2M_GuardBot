import os
import re
import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# ===== Gemini =====
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-3.6-flash")
else:
    gemini_model = None
    print("⚠️ GOOGLE_API_KEY تنظیم نشده!")

# ===== ChatGPT (OpenAI) =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def get_ai_response(text, model_type="gemini"):
    """دریافت پاسخ از مدل انتخاب شده"""
    try:
        if model_type == "gemini" and gemini_model:
            response = gemini_model.generate_content(text)
            return response.text[:4000]
        
        elif model_type == "chatgpt" and OPENAI_API_KEY:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": text}],
                max_tokens=1000
            )
            return response.choices[0].message.content[:4000]
        
        else:
            return "❌ مدل انتخاب شده در دسترس نیست. لطفاً مدل دیگری را انتخاب کنید."
            
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# ===== تابع ai_handler (برای گروه) =====
async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ در گروه (با تگ شدن)"""
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
    
    model_type = context.user_data.get("ai_model", "gemini")
    
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    reply = await get_ai_response(question, model_type)
    
    await thinking.delete()
    await update.message.reply_text(reply)

# ===== تابع ai_private_chat (برای پی‌وی) =====
async def ai_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ در پی‌وی (بدون تگ)"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    if not user:
        return
    
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("🧐 چی بپرسم؟")
        return
    
    model_type = context.user_data.get("ai_model", "gemini")
    
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    reply = await get_ai_response(text, model_type)
    
    await thinking.delete()
    await update.message.reply_text(
        reply,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
        ])
    )
