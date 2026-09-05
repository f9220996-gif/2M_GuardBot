# -*- coding: utf-8 -*-
"""
چند بازی کوچیک و فان برای وقت بیکاری در گروه:
تاس، شیر یا خط، سنگ‌کاغذقیچی (دو نفره، ۳ راند، با دکمه)، حدس عدد
"""

import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes


async def cmd_tas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پرتاب تاس واقعی تلگرام (انیمیشن دار)"""
    await update.effective_message.reply_dice(emoji="🎲")


async def cmd_shir_khat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["شیر 🦁", "خط 〰️"])
    await update.effective_message.reply_text(f"🪙 نتیجه: {result}")


# ---------------------------------------------------------------------------
# سنگ‌کاغذقیچی: یک راند.
# ریپلای روی پیام کسی = چالش مستقیم با همون شخص. بدون ریپلای = بازی با ربات.
# ---------------------------------------------------------------------------

CHOICES = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}


def _beats(a, b):
    return (
        (a == "سنگ" and b == "قیچی") or
        (a == "کاغذ" and b == "سنگ") or
        (a == "قیچی" and b == "کاغذ")
    )


def _rps_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨", callback_data="rps_pick:سنگ"),
        InlineKeyboardButton("📄", callback_data="rps_pick:کاغذ"),
        InlineKeyboardButton("✂️", callback_data="rps_pick:قیچی"),
    ]])


async def cmd_sang_kaghaz_gheychi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اگه ریپلای روی پیام یه نفر باشه، مستقیم باهاش چالش شروع می‌شه.
    اگه بدون ریپلای باشه، بازی با خودِ ربات شروع می‌شه.
    """
    message = update.effective_message
    user = update.effective_user

    existing = context.chat_data.get("rps_game")
    if existing and existing.get("status") == "playing":
        await message.reply_text("⚠️ یه بازی سنگ‌کاغذقیچی از قبل تو این گروه در حال اجراست.")
        return

    reply_target = message.reply_to_message.from_user if message.reply_to_message else None

    if reply_target and not reply_target.is_bot:
        if reply_target.id == user.id:
            await message.reply_text("نمی‌تونی با خودت بازی کنی! 😄")
            return

        context.chat_data["rps_game"] = {
            "mode": "vs_player",
            "player1_id": user.id,
            "player1_name": user.full_name,
            "player2_id": reply_target.id,
            "player2_name": reply_target.full_name,
            "choices": {},
            "status": "playing",
        }
        await message.reply_text(
            f"✂️📄🪨 {user.full_name} با {reply_target.full_name} به چالش سنگ‌کاغذقیچی افتاد!\n\n"
            "هردو نفر دکمه‌ی انتخابشون رو بزنن:",
            reply_markup=_rps_keyboard()
        )
        return

    # بدون ریپلای -> بازی با ربات
    context.chat_data["rps_game"] = {
        "mode": "vs_bot",
        "player1_id": user.id,
        "player1_name": user.full_name,
        "choices": {},
        "status": "playing",
    }
    await message.reply_text(
        f"✂️📄🪨 {user.full_name}، با من بازی کن! انتخابتو بزن:",
        reply_markup=_rps_keyboard()
    )


async def rps_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, choice = query.data.split(":")
    game = context.chat_data.get("rps_game")
    user = update.effective_user

    if not game or game.get("status") != "playing":
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    # ===== حالت بازی با ربات =====
    if game["mode"] == "vs_bot":
        if user.id != game["player1_id"]:
            await query.answer("⛔️ این بازی مال تو نیست.", show_alert=True)
            return

        bot_choice = random.choice(list(CHOICES.keys()))
        await query.answer()

        if choice == bot_choice:
            result_line = f"مساوی شدیم! هر دو {CHOICES[choice]} انتخاب کردیم. 🤝"
        elif _beats(choice, bot_choice):
            result_line = f"🎉 بردی! ({CHOICES[choice]} در برابر {CHOICES[bot_choice]})"
        else:
            result_line = f"😅 باختی! ({CHOICES[bot_choice]} در برابر {CHOICES[choice]})"

        await query.edit_message_text(
            f"✂️📄🪨 نتیجه\n\n"
            f"{game['player1_name']}: {CHOICES[choice]}\n"
            f"من: {CHOICES[bot_choice]}\n\n"
            f"{result_line}"
        )
        context.chat_data["rps_game"] = None
        return

    # ===== حالت دو نفره =====
    if user.id not in (game["player1_id"], game["player2_id"]):
        await query.answer("⛔️ تو تو این بازی نیستی.", show_alert=True)
        return

    if user.id in game["choices"]:
        await query.answer("قبلاً انتخاب کردی، منتظر حریفت باش.", show_alert=True)
        return

    game["choices"][user.id] = choice
    await query.answer("✅ انتخابت ثبت شد.")

    if len(game["choices"]) < 2:
        other_name = (
            game["player2_name"] if user.id == game["player1_id"] else game["player1_name"]
        )
        try:
            await query.edit_message_text(
                f"✂️📄🪨 {game['player1_name']} 🆚 {game['player2_name']}\n\n"
                f"✅ یک نفر انتخابش رو کرد.\n"
                f"⏳ منتظر جواب {other_name}...",
                reply_markup=_rps_keyboard()
            )
        except Exception:
            pass
        return

    c1 = game["choices"][game["player1_id"]]
    c2 = game["choices"][game["player2_id"]]

    if c1 == c2:
        result_line = f"مساوی شد! هر دو {CHOICES[c1]} انتخاب کردن. 🤝"
    elif _beats(c1, c2):
        result_line = f"🏆 {game['player1_name']} برد! ({CHOICES[c1]} در برابر {CHOICES[c2]})"
    else:
        result_line = f"🏆 {game['player2_name']} برد! ({CHOICES[c2]} در برابر {CHOICES[c1]})"

    await query.edit_message_text(
        f"✂️📄🪨 نتیجه\n\n"
        f"{game['player1_name']}: {CHOICES[c1]}\n"
        f"{game['player2_name']}: {CHOICES[c2]}\n\n"
        f"{result_line}"
    )
    context.chat_data["rps_game"] = None
