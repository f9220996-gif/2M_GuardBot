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

async def track_nav_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data

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
    await send_start_panel(update, context)
    context.user_data["nav_level"] = 0
    context.user_data["nav_chat_id"] = None
