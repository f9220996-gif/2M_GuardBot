import os
import re
import json
import google.generativeai as genai
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import database as db

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-3.6-flash")

async def ai_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشخیص فحش با هوش مصنوعی فقط برای کاربران عادی"""
    
    if not update.message or not update.message.text:
        return
    
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return
    
    user = update.effective_user
    if not user:
        return
    
    # ===== چک کردن قابلیت AI Moderation =====
    if not db.is_feature_enabled(chat.id, "ai_moderation"):
        return
    
    # ===== نادیده گرفتن مدیران، مالک و سازنده =====
    try:
        member = await chat.get_member(user.id)
        if member.status in ("administrator", "creator"):
            return
    except:
        pass
    
    # ===== سازنده ربات رو هم نادیده بگیر =====
    from config import CREATOR_ID
    if user.id == CREATOR_ID:
        return
    
    # ===== چک کردن پیام =====
    text = update.message.text
    
    # اگه پیام خیلی کوتاهه، نادیده بگیر
    if len(text.strip()) < 3:
        return
    
    # ===== تشخیص با هوش مصنوعی =====
    try:
        prompt = f"""
        تو یه ربات مدیریت گروه هستی. فقط پیام‌های فارسی رو بررسی کن.
        
        پیام کاربر: "{text}"
        
        فقط به این فرمت JSON جواب بده:
        {{
            "is_bad": true/false,
            "level": 1/2/3
        }}
        
        سطح‌ها:
        1 = فحش خفیف (اخطار)
        2 = فحش متوسط (سکوت کوتاه)
        3 = فحش سنگین (سکوت طولانی)
        
        اگه پیام فحش نیست: is_bad = false
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        # استخراج JSON
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if not json_match:
            return
        
        data = json.loads(json_match.group())
        is_bad = data.get("is_bad", False)
        level = data.get("level", 1)
        
        if not is_bad:
            return
        
        # ===== حذف پیام فحش =====
        try:
            await update.message.delete()
        except:
            pass
        
        # ===== اقدام بر اساس سطح =====
        # گرفتن تنظیمات از دیتابیس
        warnings = db.get_warnings(chat.id, user.id)
        if warnings is None:
            warnings = 0
        
        # افزایش تعداد اخطار
        warnings += 1
        db.set_warnings(chat.id, user.id, warnings)
        
        # اقدام متناسب با سطح
        if level == 1:
            # اخطار با پیام
            msg = f"⚠️ {user.first_name} لطفاً ادب رو رعایت کن! (اخطار {warnings})"
            await update.message.reply_text(msg)
            
        elif level == 2:
            # سکوت ۵ دقیقه
            until = datetime.now() + timedelta(minutes=5)
            try:
                await chat.ban_member(user.id, until_date=until)
                msg = f"🔇 {user.first_name} به مدت ۵ دقیقه سکوت شد."
                await update.message.reply_text(msg)
            except:
                pass
                
        elif level >= 3:
            # سکوت ۱۰ دقیقه
            until = datetime.now() + timedelta(minutes=10)
            try:
                await chat.ban_member(user.id, until_date=until)
                msg = f"🔇 {user.first_name} به مدت ۱۰ دقیقه سکوت شد."
                await update.message.reply_text(msg)
            except:
                pass
                
    except Exception as e:
        print(f"AI Moderation Error: {e}")
