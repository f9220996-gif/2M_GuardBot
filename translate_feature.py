# -*- coding: utf-8 -*-
"""
قابلیت ترجمه:
- با ریپلای روی یه پیام و نوشتن «ترجمه»
- یا گذاشتن یه کلمه‌ی فعال‌ساز (پیش‌فرض: نقطه «.») جلوی متن (مثلاً: .hello)
زبان مقصد و کلمه‌ی فعال‌ساز از پنل مدیریت گروه قابل تنظیمن.
"""

import re
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import can_access_dm_panel

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

DEFAULT_TRIGGER = "."


def get_translate_trigger(chat_id):
    return db.get_setting(f"translate_trigger_{chat_id}", DEFAULT_TRIGGER)


def set_translate_trigger(chat_id, trigger):
    db.set_setting(f"translate_trigger_{chat_id}", trigger)


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
    if not db.is_feature_enabled(chat.id, "translate"):
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
    """اگه پیام با کلمه‌ی فعال‌ساز شروع بشه، همون متن ترجمه می‌شه. True یعنی مصرف شد."""
    chat = update.effective_chat
    message = update.effective_message
    if not chat or chat.type not in ("group", "supergroup"):
        return False
    if not db.is_feature_enabled(chat.id, "translate"):
        return False

    trigger = get_translate_trigger(chat.id)
    text = (message.text or "").strip()
    if not trigger or not text.startswith(trigger) or len(text) <= len(trigger):
        return False

    to_translate = text[len(trigger):].strip()
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
# پنل انتخاب زبان مقصد ترجمه + کلمه‌ی فعال‌ساز
# ---------------------------------------------------------------------------

def _translate_panel_text(chat_id, extra_line=None):
    current = db.get_translate_lang(chat_id)
    trigger = get_translate_trigger(chat_id)
    status = "✔ فعال" if db.is_feature_enabled(chat_id, "translate") else "✘ غیرفعال"
    text = (
        "🌐 تنظیمات ترجمه\n\n"
        f"وضعیت: {status}\n"
        f"زبان مقصد فعلی: {LANGUAGES.get(current, current)}\n"
        f"کلمه‌ی فعال‌ساز فعلی: «{trigger}»\n\n"
        "یه زبان انتخاب کن، یا کلمه‌ی فعال‌ساز رو تغییر بده:"
    )
    if extra_line:
        text = f"{extra_line}\n\n{text}"
    return text


def _translate_panel_keyboard(chat_id):
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
    rows.append([InlineKeyboardButton("✏️ تغییر کلمه‌ی فعال‌ساز", callback_data=f"tr_trigger:{chat_id}")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])
    return InlineKeyboardMarkup(rows)


async def open_translate_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.edit_message_text(_translate_panel_text(chat_id), reply_markup=_translate_panel_keyboard(chat_id))


async def set_translate_lang_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, code = query.data.split(":")
    chat_id = int(chat_id)
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    db.set_translate_lang(chat_id, code)
    await query.answer("ذخیره شد ✔")
    await query.edit_message_text(_translate_panel_text(chat_id), reply_markup=_translate_panel_keyboard(chat_id))


async def ask_set_translate_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست کلمه‌ی فعال‌ساز جدید برای ترجمه"""
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return
    await query.answer()

    context.user_data["waiting_translate_trigger_chat_id"] = chat_id
    context.user_data["translate_prompt_chat_id"] = query.message.chat_id
    context.user_data["translate_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ انصراف", callback_data=f"tr_panel:{chat_id}")]])
    await query.edit_message_text(
        "✏️ کلمه یا نشونه‌ی فعال‌ساز ترجمه رو بفرست.\n\n"
        f"فعلی: «{get_translate_trigger(chat_id)}»\n"
        "مثلاً می‌تونی همین «.» رو نگه داری، یا چیزی مثل «:» یا «ترجمه:» بفرستی.\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb
    )


async def receive_translate_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت کلمه‌ی فعال‌ساز جدید. True یعنی پیام مصرف شد."""
    chat_id = context.user_data.get("waiting_translate_trigger_chat_id")
    if not chat_id:
        return False

    user = update.effective_user
    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        return False

    context.user_data["waiting_translate_trigger_chat_id"] = None
    prompt_chat_id = context.user_data.pop("translate_prompt_chat_id", None)
    prompt_message_id = context.user_data.pop("translate_prompt_message_id", None)

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
        set_translate_trigger(chat_id, new_trigger)
        confirm = f"✔ کلمه‌ی فعال‌ساز ترجمه به «{new_trigger}» تغییر کرد."

    text = _translate_panel_text(chat_id, extra_line=confirm)
    kb = _translate_panel_keyboard(chat_id)

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
