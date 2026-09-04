# -*- coding: utf-8 -*-
"""
میان‌برهای قابل‌تغییر دستورات گروه.
هر گروه می‌تونه کلمه‌ی هرکدوم از دستورات (مثل «سکوت»، «بن کن»، «پاک»، ...) رو
با یه کلمه‌ی دلخواه خودش عوض کنه. کلید اصلی (که تابع واقعی رو صدا می‌زنه)
همیشه همون کلید پیش‌فرضه؛ فقط کلمه‌ای که کاربر تایپ می‌کنه قابل‌تغییره.
"""

import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import database as db
from permissions import can_access_dm_panel

# کلید پیش‌فرض -> برچسب فارسی نمایشی (فقط برای نمایش تو پنل)
DEFAULT_COMMANDS = {
    "خاموشی": "قفل گروه",
    "روشن": "باز کردن گروه",
    "سکوت": "سکوت دادن",
    "آزاد کن": "آزاد کردن",
    "بن کن": "بن کردن",
    "اخطار": "اخطار",
    "پاک": "پاک کردن پیام",
    "گیف بن": "بن کردن گیف",
    "استیکر بن": "بن کردن استیکر",
    "تاس": "بازی تاس",
    "شیر یا خط": "شیر یا خط",
    "سنگ کاغذ قیچی": "سنگ‌کاغذقیچی",
    "گزارش": "گزارش کاربر",
    "ترجمه": "ترجمه",
    "تاریخ": "تاریخ",
    "رمز ارز": "قیمت‌ها",
}
COMMAND_ICONS = {
    "خاموشی": "🔒",
    "روشن": "🔓",
    "سکوت": "🔇",
    "آزاد کن": "🔊",
    "بن کن": "⛔️",
    "اخطار": "⚠️",
    "پاک": "🗑",
    "گیف بن": "🚫",
    "استیکر بن": "🚫",
    "تاس": "🎲",
    "شیر یا خط": "🪙",
    "سنگ کاغذ قیچی": "✊",
    "گزارش": "📩",
    "ترجمه": "🌐",
    "تاریخ": "📅",
    "رمز ارز": "💰",
}
COMMAND_KEYS_ORDER = list(DEFAULT_COMMANDS.keys())


def get_command_aliases(chat_id):
    """dict: کلید پیش‌فرض -> کلمه‌ی سفارشیِ همین گروه (فقط مواردی که تغییر کردن)"""
    raw = db.get_setting(f"cmd_aliases_{chat_id}")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _save_aliases(chat_id, aliases):
    db.set_setting(f"cmd_aliases_{chat_id}", json.dumps(aliases, ensure_ascii=False))


def set_command_alias(chat_id, key, new_word):
    aliases = get_command_aliases(chat_id)
    aliases[key] = new_word
    _save_aliases(chat_id, aliases)


def reset_command_alias(chat_id, key):
    aliases = get_command_aliases(chat_id)
    aliases.pop(key, None)
    _save_aliases(chat_id, aliases)


def reset_all_command_aliases(chat_id):
    _save_aliases(chat_id, {})


def get_active_keyword(chat_id, key):
    return get_command_aliases(chat_id).get(key, key)


def get_group_command_keywords(chat_id):
    """
    برمی‌گردونه: {کلمه‌ی فعلی (سفارشی یا پیش‌فرض): کلید اصلی}
    این نگاشت تو main.py برای تشخیص اینکه کاربر چی تایپ کرده استفاده می‌شه.
    """
    aliases = get_command_aliases(chat_id)
    return {aliases.get(key, key): key for key in DEFAULT_COMMANDS}


# ---------------------------------------------------------------------------
# پنل تنظیم میان‌برها
# ---------------------------------------------------------------------------

def _shortcuts_panel_text(chat_id, extra_line=None):
    legend = "\n".join(
        f"{COMMAND_ICONS.get(key, '•')} {DEFAULT_COMMANDS[key]}"
        for key in COMMAND_KEYS_ORDER
    )
    text = (
        "🔤 میان‌برهای دستورات گروه\n\n"
        f"{legend}\n\n"
        "روی هرکدوم از دکمه‌های زیر بزن تا کلمه‌ی همون دستور رو عوض کنی:"
    )
    if extra_line:
        text = f"{extra_line}\n\n{text}"
    return text


def _shortcuts_panel_keyboard(chat_id):
    rows = []
    line = []
    for i, key in enumerate(COMMAND_KEYS_ORDER):
        icon = COMMAND_ICONS.get(key, "•")
        active = get_active_keyword(chat_id, key)
        line.append(InlineKeyboardButton(f"{icon} «{active}»", callback_data=f"cmdalias_edit:{chat_id}:{i}"))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton("🧠 فعال‌ساز هوش مصنوعی", callback_data=f"ai_trigger_panel:{chat_id}")])
    rows.append([InlineKeyboardButton("🔄 بازنشانی همه به پیش‌فرض", callback_data=f"cmdalias_resetall:{chat_id}")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"grp_open:{chat_id}")])
    return InlineKeyboardMarkup(rows)


async def open_shortcuts_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    await query.edit_message_text(_shortcuts_panel_text(chat_id), reply_markup=_shortcuts_panel_keyboard(chat_id))


async def ask_edit_command_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, idx = query.data.split(":")
    chat_id, idx = int(chat_id), int(idx)
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    if idx < 0 or idx >= len(COMMAND_KEYS_ORDER):
        await query.answer("این مورد پیدا نشد.", show_alert=True)
        return
    key = COMMAND_KEYS_ORDER[idx]
    await query.answer()

    context.user_data["waiting_cmdalias"] = (chat_id, key)
    context.user_data["cmdalias_prompt_chat_id"] = query.message.chat_id
    context.user_data["cmdalias_prompt_message_id"] = query.message.message_id

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ برگردوندن به پیش‌فرض", callback_data=f"cmdalias_reset:{chat_id}:{idx}")],
        [InlineKeyboardButton("⬅️ انصراف", callback_data=f"cmdshortcuts_panel:{chat_id}")],
    ])
    await query.edit_message_text(
        f"✏️ کلمه‌ی جدید برای «{DEFAULT_COMMANDS[key]}» رو بفرست.\n\n"
        f"پیش‌فرض: «{key}»\n"
        f"فعلی: «{get_active_keyword(chat_id, key)}»\n\n"
        "برای لغو، دستور /cancel را بفرستید.",
        reply_markup=kb
    )


async def receive_command_alias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    pending = context.user_data.get("waiting_cmdalias")
    if not pending:
        return False
    chat_id, key = pending
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        return False

    context.user_data["waiting_cmdalias"] = None
    prompt_chat_id = context.user_data.pop("cmdalias_prompt_chat_id", None)
    prompt_message_id = context.user_data.pop("cmdalias_prompt_message_id", None)

    new_word = (update.effective_message.text or "").strip()

    try:
        await update.effective_message.delete()
    except Exception:
        pass

    if new_word == "/cancel":
        confirm = "❌ لغو شد."
    elif not new_word:
        confirm = "❗️ چیزی دریافت نشد، تغییری اعمال نشد."
    else:
        set_command_alias(chat_id, key, new_word)
        confirm = f"✔ کلمه‌ی «{DEFAULT_COMMANDS[key]}» به «{new_word}» تغییر کرد."

    text = _shortcuts_panel_text(chat_id, extra_line=confirm)
    kb = _shortcuts_panel_keyboard(chat_id)

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


async def reset_command_alias_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id, idx = query.data.split(":")
    chat_id, idx = int(chat_id), int(idx)
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    if 0 <= idx < len(COMMAND_KEYS_ORDER):
        reset_command_alias(chat_id, COMMAND_KEYS_ORDER[idx])

    await query.answer("✔ به پیش‌فرض برگشت")
    await query.edit_message_text(_shortcuts_panel_text(chat_id), reply_markup=_shortcuts_panel_keyboard(chat_id))


async def reset_all_command_aliases_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = update.effective_user

    if not await can_access_dm_panel(context.bot, chat_id, user.id):
        await query.answer("⛔️ اجازه ندارید.", show_alert=True)
        return

    reset_all_command_aliases(chat_id)
    await query.answer("✔ همه به پیش‌فرض برگشتن")
    await query.edit_message_text(_shortcuts_panel_text(chat_id), reply_markup=_shortcuts_panel_keyboard(chat_id))


# ---------------------------------------------------------------------------
# دستور «راهنما» تو خودِ گروه - همیشه کلمه‌های فعلیِ همین گروه رو نشون می‌ده
# ---------------------------------------------------------------------------

def build_group_help_text(chat_id):
    pairs = []
    line = []
    for key in COMMAND_KEYS_ORDER:
        icon = COMMAND_ICONS.get(key, "•")
        active = get_active_keyword(chat_id, key)
        line.append(f"{icon} {active}")
        if len(line) == 2:
            pairs.append("   ".join(line))
            line = []
    if line:
        pairs.append("   ".join(line))
    body = "\n".join(pairs)
    return f"📖 راهنمای دستورات این گروه\n\n{body}"


async def cmd_group_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return
    await update.effective_message.reply_text(build_group_help_text(chat.id))
