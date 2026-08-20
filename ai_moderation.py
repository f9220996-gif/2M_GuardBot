import os
import re
import json
import google.generativeai as genai
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import database as db

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

async def ai_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return
    
    user = update.effective_user
    if not user:
        return
    
    # چک کردن قابلیت AI Moderation
    if not db.is_feature_enabled(chat.id, "ai_moderation"):
        return
    
    # نادیده گرفتن مدیران، مالک و سازنده
    try:
        member = await chat.get_member(user.id)
        if member.status in ("administrator", "creator"):
            return
    except:
        pass
    
    from config import CREATOR_ID
    if user.id == CREATOR_ID:
        return
    
    text = update.message.text
    if len(text.strip()) < 3:
        return
    
    try:
        prompt = f"""
        تو یه ربات مدیریت گروه هستی. فقط پیام‌های فارسی رو بررسی کن.
        
        پیام کاربر: "{text}"
        
        فقط به این فرمت JSON جواب بده:
        {{"is_bad": true/false, "level": 1/2/3}}
        
        سطح‌ها:
        1 = فحش خفیف (اخطار)
        2 = فحش متوسط (سکوت ۵ دقیقه)
        3 = فحش سنگین (سکوت ۱۰ دقیقه)
        
        اگه پیام فحش نیست: is_bad = false
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if not json_match:
            return
        
        data = json.loads(json_match.group())
        is_bad = data.get("is_bad", False)
        level = data.get("level", 1)
        
        if not is_bad:
            return
        
        # حذف پیام فحش
        try:
            await update.message.delete()
        except:
            pass
        
        username = f"@{user.username}" if user.username else user.full_name
        
        # اقدام بر اساس سطح
        if level == 1:
            await update.message.reply_text(f"⚠️ {username} لطفاً ادب رو رعایت کن!")
        elif level == 2:
            until = datetime.now() + timedelta(minutes=5)
            try:
                await chat.ban_member(user.id, until_date=until)
                await update.message.reply_text(f"🔇 {username} به مدت ۵ دقیقه سکوت شد.")
            except:
                pass
        elif level >= 3:
            until = datetime.now() + timedelta(minutes=10)
            try:
                await chat.ban_member(user.id, until_date=until)
                await update.message.reply_text(f"🔇 {username} به مدت ۱۰ دقیقه سکوت شد.")
            except:
                pass
                
    except Exception as e:
        print(f"AI Moderation Error: {e}")
