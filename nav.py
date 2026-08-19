# -*- coding: utf-8 -*-
"""
ردیابی ساده‌ی اینکه کاربر الان تو کدوم سطح از پنل هست، تا دکمه ثابت
«◀️ صفحه قبل» بتونه یک قدم برگرده (برخلاف «🔙 منوی اصلی» که کامل برمی‌گرده).

سطح‌ها:
0 = منوی اصلی
1 = لیست گروه‌ها
2 = پنل یک گروه خاص
3 = هر زیرصفحه‌ی دیگه (بن‌شده‌ها، سکوت‌خورده‌ها، قابلیت‌ها، خوش‌آمدگویی، و...)
"""

from telegram import Update
from telegram.ext import ContextTypes

LEVEL0_PREFIXES = ("start_menu", "help_commands", "creator_panel_open")
LEVEL1_PREFIXES = ("panel_my_groups", "grp_active_on:", "grp_active_off:")
LEVEL2_PREFIXES = ("grp_open:",)
# هر چیز دیگه‌ای که با چک‌باکس‌های شناخته‌شده شروع بشه، سطح ۳ حساب می‌شه
# این‌ها گزارش رو با report_id (نه chat_id) صدا می‌زنن؛ نباید chat_id ذخیره‌شده رو خراب کنن
LEVEL3_NO_CHATID_PREFIXES = ("report_open:", "report_act:")

LEVEL3_PREFIXES = (
    "grp_banned:", "grp_muted:", "grp_warned:", "grp_features:", "feat_toggle:",
    "wc_", "grp_reports:", "reports_clear:",
    "warnedit_", "tr_panel:", "tr_set:",
    "cln_", "mute_",
    "report_open:", "report_act:", "imglang_",
)


async def track_nav_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قبل از هر هندلر دیگه‌ای (group=-1) اجرا می‌شه و وضعیت رو ثبت می‌کنه؛
    وقتی از منوی اصلی خارج/واردش می‌شیم، دکمه‌ی ثابت پایین رو نشون/مخفی می‌کنه"""
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

    prev_level = context.user_data.get("nav_level", 0)

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
    else:
        return  # این دکمه ربطی به پیمایش نداشت، چیزی عوض نشد

    new_level = context.user_data.get("nav_level", 0)
    if new_level == prev_level:
        return

    chat = update.effective_chat
    if not chat or chat.type != "private":
        return

    if new_level == 0 and prev_level != 0:
        # برگشتیم به منوی اصلی -> دکمه ثابت پایین رو مخفی کن
        from telegram import ReplyKeyboardRemove
        try:
            msg = await context.bot.send_message(chat.id, "🏠", reply_markup=ReplyKeyboardRemove())
            context.job_queue.run_once(
                _delete_hint_later, when=1,
                data={"chat_id": chat.id, "message_id": msg.message_id},
                name=f"delhint_{chat.id}_{msg.message_id}"
            )
        except Exception:
            pass
    elif new_level != 0 and prev_level == 0:
        # از منوی اصلی خارج شدیم -> دکمه ثابت پایین رو نشون بده
        from start import PERSISTENT_KEYBOARD
        try:
            msg = await context.bot.send_message(chat.id, "🔽", reply_markup=PERSISTENT_KEYBOARD)
            context.job_queue.run_once(
                _delete_hint_later, when=1,
                data={"chat_id": chat.id, "message_id": msg.message_id},
                name=f"delhint_{chat.id}_{msg.message_id}"
            )
        except Exception:
            pass


async def _delete_hint_later(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass


async def handle_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه ثابت «◀️ صفحه قبل» رو مدیریت می‌کنه"""
    from start import send_start_panel
    from panel import show_my_groups, send_group_panel_message

    level = context.user_data.get("nav_level", 0)
    chat_id = context.user_data.get("nav_chat_id")

    if level >= 3 and chat_id:
        await send_group_panel_message(update, context, chat_id)
        context.user_data["nav_level"] = 2
        return

    if level == 2 and chat_id:
        await show_my_groups(update, context)
        context.user_data["nav_level"] = 1
        context.user_data["nav_chat_id"] = None
        return

    # سطح ۰ یا ۱ یا هر حالت نامشخص -> برو منوی اصلی (و کیبورد ثابت رو مخفی کن)
    await send_start_panel(update, context)
    if level != 0:
        from telegram import ReplyKeyboardRemove
        try:
            msg = await update.effective_message.reply_text("🏠", reply_markup=ReplyKeyboardRemove())
            context.job_queue.run_once(
                _delete_hint_later, when=1,
                data={"chat_id": update.effective_chat.id, "message_id": msg.message_id},
                name=f"delhint_{update.effective_chat.id}_{msg.message_id}"
            )
        except Exception:
            pass
    context.user_data["nav_level"] = 0
    context.user_data["nav_chat_id"] = None
