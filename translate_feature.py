# -*- coding: utf-8 -*-
"""
قابلیت ترجمه:
- با ریپلای روی یه پیام و نوشتن «ترجمه»
- یا گذاشتن یه نقطه «.» جلوی متن (مثلاً: .hello)
زبان مقصد از پنل مدیریت گروه قابل تنظیمه.
"""

import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import is_creator, is_group_owner

LANGUAGES = {
    "fa": "فارسی",
    "en": "انگلیسی",
    "ar": "عربی",
    "tr": "ترکی",
    "ru": "روسی",
    "fr": "فرانسه",
    "es": "اسپانیایی",
    "de": "آلمانی",
    "zh-CN": "چینی",
}


def translate_text(text: str, target_lang: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # data[0] لیستی از تکه‌های ترجمه‌شده‌ست
    return "".join(part[0] for part in data[0] if part[0])


async def cmd_tarjome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور «ترجمه» با ریپلای روی یه پیام"""
    chat = update.effective_chat
    message = update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        return
    if not message.reply_to_message:
        await message.reply_text("❗️ روی پیام مورد نظر ریپلای کن و بنویس: ترجمه")
        return

    source_text = message.reply_to_message.text or message.reply_to_message.caption
    if not source_text:
        await message.reply_text("❗️ این پیام متنی برای ترجمه نداره.")
        return

    target_lang = db.get_translate_lang(chat.id)
    try:
        translated = translate_text(source_text, target_lang)
    except Exception as e:
        await message.reply_text(f"✘ ترجمه انجام نشد.\n{e}")
        return

    await message.reply_text(f"🌐 ترجمه ({LANGUAGES.get(target_lang, target_lang)}):\n{translated}")


async def check_dot_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگه پیام با نقطه شروع بشه، همون متن ترجمه می‌شه. True یعنی مصرف شد."""
    chat = update.effective_chat
    message = update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        return False

    text = (message.text or "").strip()
    if not text.startswith(".") or len(text) < 2:
        return False

    to_translate = text[1:].strip()
    if not to_translate:
        return False

    target_lang = db.get_translate_lang(chat.id)
    try:
        translated = translate_text(to_translate, target_lang)
    except Exception as e:
        await message.reply_text(f"✔ ترجمه انجام نشد.\n{e}")
        return True

    await message.reply_text(f"🌐 ترجمه ({LANGUAGES.get(target_lang, target_lang)}):\n{translated}")
    return True


# ---------------------------------------------------------------------------
# پنل انتخاب زبان مقصد ترجمه
# ---------------------------------------------------------------------------

async def _user_can_manage(bot, user_id, chat_id):
    if await is_creator(user_id):
        return True
    return await is_group_owner(chat_id, user_id)


async def open_translate_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    current = db.get_translate_lang(chat_id)
    rows = []
    line = []
    for code, name in LANGUAGES.items():
        mark = "✔ " if code == current else ""
        line.append(InlineKeyboardButton(f"{mark}{name}", callback_data=f"tr_set:{chat_id}:{code}"))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])

    await query.edit_message_text(
        f"🌐 زبان مقصد ترجمه\n\nفعلی: {LANGUAGES.get(current, current)}\n\nیکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def set_translate_lang_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, code = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await _user_can_manage(context.bot, user.id, chat_id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_translate_lang(chat_id, code)
    await query.answer("ذخیره شد ✔")
    await open_translate_panel(update, context)
