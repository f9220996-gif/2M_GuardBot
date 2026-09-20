# -*- coding: utf-8 -*-
"""
ردیابی ساده‌ی اینکه کاربر الان تو کدوم سطح از پنل هست.
"""

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes

LEVEL0_PREFIXES = ("start_menu", "help_commands", "creator_panel_open", "restart_bot", "ai_model_select", "ai_use_gemini", "ai_use_chatgpt")
LEVEL1_PREFIXES = ("panel_my_groups", "grp_active_on:", "grp_active_off:")
LEVEL2_PREFIXES = ("grp_open:",)
LEVEL3_NO_CHATID_PREFIXES = ("report_open:", "report_act:")
LEVEL3_PREFIXES = (
    "grp_banned:", "grp_muted:", "grp_warned:", "grp_features:", "feat_toggle:",
    "wc_", "grp_reports:", "reports_clear:",
    "warnedit_", "tr_panel:", "tr_set:",
    "cln_", "mute_",
    "report_open:", "report_act:", "imglang_",
)


def _clear_waiting_states(context: ContextTypes.DEFAULT_TYPE):
    """
    باگ: پرچم‌های «منتظر متن بعدی» (مثل waiting_for_update_msg،
    waiting_for_shutdown_text، waiting_for_bad_word_chat_id،
    waiting_ai_trigger_chat_id و مشابه‌هاشون) وقتی با دکمه‌ی
    «⬅️ بازگشت» یا هر دکمه‌ی دیگه‌ای از اون مرحله خارج می‌شدیم،
    هیچ‌وقت پاک نمی‌شدن. نتیجه‌ش این بود که پیام بعدی که کاربر
    برای هر منظور دیگه‌ای می‌فرستاد (مثلاً چت با هوش مصنوعی)،
    به‌اشتباه به‌عنوان همون متن قدیمی (مثلاً «پیام آپدیت») ثبت می‌شد.

    چون این تابع رو *هر* دکمه‌ی شیشه‌ای (قبل از هر هندلر دیگه‌ای،
    group=-1) اجرا می‌شه، اینجا بهترین جاست که همه‌ی این پرچم‌ها
    پاک بشن: زدن هر دکمه‌ای یعنی کاربر دیگه تو حالت «داره تایپ
    می‌کنه برای اون درخواست قبلی» نیست.
    """
    for key in list(context.user_data.keys()):
        if key.startswith("waiting_"):
            context.user_data.pop(key, None)


async def track_nav_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data

    _clear_waiting_states(context)

    parts = data.split(":")
    chat_id = None
    if len(parts) >= 2:
        try:
            chat_id = int(parts[1])
        except ValueError:
            chat_id = None

    if any(data.startswith(p) for p in LEVEL0_PREFIXES):
        context.user_data["nav_level"] = 0
        context.user_data["nav_chat_id"] = None
    elif any(data.startswith(p) for p in LEVEL1_PREFIXES):
        context.user_data["nav_level"] = 1
        context.user_data["nav_chat_id"] = None
    elif any(data.startswith(p) for p in LEVEL2_PREFIXES):
        context.user_data["nav_level"] = 2
        context.user_data["nav_chat_id"] = chat_id
    elif any(data.startswith(p) for p in LEVEL3_PREFIXES):
        context.user_data["nav_level"] = 3
        if not any(data.startswith(p) for p in LEVEL3_NO_CHATID_PREFIXES):
            context.user_data["nav_chat_id"] = chat_id


async def handle_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه صفحه قبل (حذف شده) - فقط برمیگرده به منو"""
    from start import send_start_panel
    _clear_waiting_states(context)
    await send_start_panel(update, context)
    context.user_data["nav_level"] = 0
    context.user_data["nav_chat_id"] = None
