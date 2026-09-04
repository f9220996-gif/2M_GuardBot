import os
import re
import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import can_access_dm_panel

DEFAULT_AI_TRIGGER = "/Bot"


def get_ai_trigger(chat_id):
    return db.get_setting(f"ai_trigger_{chat_id}", DEFAULT_AI_TRIGGER)


def set_ai_trigger(chat_id, trigger):
    db.set_setting(f"ai_trigger_{chat_id}", trigger)


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
    """پاسخ در گروه (با تگ شدن با کلمه‌ی فعال‌ساز، پیش‌فرض /Bot)"""
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    if not db.is_feature_enabled(chat.id, "ai_chat"):
        return

    text = update.message.text
    bot_username = context.bot.username
    trigger = get_ai_trigger(chat.id)

    # ===== چک کردن کلمه‌ی فعال‌ساز (قابل‌تنظیم) یا منشن مستقیم ربات =====
    if trigger not in text and f"/{bot_username}" not in text:
        return
    # ========================================================================

    # ===== پاک کردن تگ از متن =====
    question = re.sub(re.escape(trigger) + r"\s*", "", text)
    question = re.sub(f"/{re.escape(bot_username)}" + r"\s*", "", question)
    question = question.strip()
    # ================================
    
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
    chat = update.effective_chat
    if not user or not chat:
        return
    
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("🧐 چی بپرسم؟")
        return
    
    model_type = context.user_data.get("ai_model", "gemini")
    
    thinking = await update.message.reply_text("🤔 دارم فکر می‌کنم...")
    
    reply = await get_ai_response(text, model_type)
    
    await thinking.delete()

    # ===== پاک کردن پنل/پیام قبلی، چون این پیام با دکمه «بازگشت» جاش رو می‌گیره =====
    old_msg_id = db.get_setting(f"panel_msg_{chat.id}")
    if old_msg_id:
        try:
            await context.bot.delete_message(chat.id, int(old_msg_id))
        except Exception:
            pass
    # ===================================================================================

    sent = await update.message.reply_text(
        reply,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="start_menu")]
        ])
    )

    # ===== ثبت این پیام به‌عنوان «پنل فعلی» =====
    db.set_setting(f"panel_msg_{chat.id}", str(sent.message_id))
    # ===============================================


# ---------------------------------------------------------------------------
# پنل تغییر کلمه‌ی فعال‌ساز هوش مصنوعی تو گروه
# ---------------------------------------------------------------------------

def _ai_trigger_panel_text(chat_id, extra_line=None):
    text = (
        "🧠 کلمه‌ی فعال‌ساز هوش مصنوعی تو گروه\n\n"
        f"فعلی: «{get_ai_trigger(chat_id)}»\n\n"
        "برای صحبت با هوش مصنوعی تو گروه، باید این کلمه (یا منشن مستقیم ربات) اول پیام باشه."
    )
    if extra_line:
        text = f"{extra_line}\n\n{text}"
    return text


def _ai_trigger_panel_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تغییر کلمه‌ی فعال‌ساز", callback_data=f"ai_trigger_set:{chat_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"cmdshortcuts_panel:{chat_id}")],
    ])


async def open_ai_trigger_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.edit_message_text(_ai_trigger_panel_text(chat_id), reply_markup=_ai_trigger_panel_keyboard(chat_id))


async def ask_set_ai_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data["waiting_ai_trigger_chat_id"] = chat_id
    context.user_data["ai_trigger_prompt_chat_id"] = query.message.chat_id
    context.user_data["ai_trigger_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"ai_trigger_panel:{chat_id}")]])
    await query.edit_message_text(
        "✏️ کلمه‌ی جدید برای فعال‌سازی هوش مصنوعی تو گروه رو بفرست.\n\n"
        f"فعلی: «{get_ai_trigger(chat_id)}»\n"
        "مثلاً: /Bot یا هر کلمه‌ی دیگه‌ای که دوست داری.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb
    )


async def receive_ai_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = context.user_data.get("waiting_ai_trigger_chat_id")
    if not chat_id:
        return False

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        return False

    context.user_data["waiting_ai_trigger_chat_id"] = None
    prompt_chat_id = context.user_data.pop("ai_trigger_prompt_chat_id", None)
    prompt_message_id = context.user_data.pop("ai_trigger_prompt_message_id", None)

    new_trigger = (update.effective_message.text or "").strip()

    try:
        await update.effective_message.delete()
    except Exception:
        pass

    if new_trigger == "/cancel":
        confirm = "❌ لغو شد."
    elif not new_trigger:
        confirm = "❗️ چیزی دریافت نشد، تغییری اعمال نشد."
    else:
        set_ai_trigger(chat_id, new_trigger)
        confirm = f"✔ کلمه‌ی فعال‌ساز هوش مصنوعی به «{new_trigger}» تغییر کرد."

    text = _ai_trigger_panel_text(chat_id, extra_line=confirm)
    kb = _ai_trigger_panel_keyboard(chat_id)

    if prompt_chat_id and prompt_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=prompt_chat_id, message_id=prompt_message_id,
                text=text, reply_markup=kb
            )
            return True
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb)
    return True
