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
# سنگ‌کاغذقیچی: دو نفره، ۳ راند، با دکمه‌های شیشه‌ای
# ---------------------------------------------------------------------------

CHOICES = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}
TOTAL_ROUNDS = 1


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


def _round_text(game, extra=""):
    text = (
        f"✂️📄🪨 راند {game['round']}/{TOTAL_ROUNDS}\n\n"
        f"{game['player1_name']} 🆚 {game['player2_name']}\n"
        f"امتیاز: {game['score1']} - {game['score2']}\n\n"
        "هرکس دکمه‌ی انتخابش رو بزنه (فقط این دو نفر می‌تونن انتخاب کنن):"
    )
    if extra:
        text = f"{extra}\n\n{text}"
    return text


async def cmd_sang_kaghaz_gheychi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع یه چالش سنگ‌کاغذقیچی دو نفره، ۳ راند"""
    message = update.effective_message
    user = update.effective_user

    existing = context.chat_data.get("rps_game")
    if existing and existing.get("status") in ("waiting", "playing"):
        await message.reply_text("⚠️ یه بازی سنگ‌کاغذقیچی از قبل تو این گروه در حال اجراست.")
        return

    context.chat_data["rps_game"] = {
        "player1_id": user.id,
        "player1_name": user.full_name,
        "player2_id": None,
        "player2_name": None,
        "round": 1,
        "score1": 0,
        "score2": 0,
        "choices": {},
        "status": "waiting",
    }

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 قبول چالش", callback_data="rps_join")]])
    await message.reply_text(
        f"✂️📄🪨 {user.full_name} یه بازی سنگ‌کاغذقیچی (۳ راند) شروع کرد!\n\n"
        "کی می‌خواد باهاش بازی کنه؟",
        reply_markup=kb
    )


async def rps_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game = context.chat_data.get("rps_game")
    user = update.effective_user

    if not game or game.get("status") != "waiting":
        await query.answer("این چالش دیگه فعال نیست.", show_alert=True)
        return
    if user.id == game["player1_id"]:
        await query.answer("نمی‌تونی با خودت بازی کنی! 😄", show_alert=True)
        return

    game["player2_id"] = user.id
    game["player2_name"] = user.full_name
    game["status"] = "playing"
    await query.answer("وارد بازی شدی! 🎮")

    await query.edit_message_text(_round_text(game), reply_markup=_rps_keyboard())


async def rps_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, choice = query.data.split(":")
    game = context.chat_data.get("rps_game")
    user = update.effective_user

    if not game or game.get("status") != "playing":
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    if user.id not in (game["player1_id"], game["player2_id"]):
        await query.answer("⛔️ تو تو این بازی نیستی.", show_alert=True)
        return

    if user.id in game["choices"]:
        await query.answer("قبلاً انتخاب کردی، منتظر حریفت باش.", show_alert=True)
        return

    game["choices"][user.id] = choice
    await query.answer("✅ انتخابت ثبت شد.")

    if len(game["choices"]) < 2:
        return  # هنوز نفر دوم انتخاب نکرده

    c1 = game["choices"][game["player1_id"]]
    c2 = game["choices"][game["player2_id"]]

    if c1 == c2:
        result_line = f"این راند مساوی شد! هر دو {CHOICES[c1]} انتخاب کردن."
    elif _beats(c1, c2):
        game["score1"] += 1
        result_line = f"🎉 {game['player1_name']} این راند رو برد! ({CHOICES[c1]} در برابر {CHOICES[c2]})"
    else:
        game["score2"] += 1
        result_line = f"🎉 {game['player2_name']} این راند رو برد! ({CHOICES[c2]} در برابر {CHOICES[c1]})"

    game["choices"] = {}

    if game["round"] >= TOTAL_ROUNDS:
        game["status"] = "finished"
        if game["score1"] > game["score2"]:
            winner_line = f"🏆 برنده‌ی نهایی: {game['player1_name']}!"
        elif game["score2"] > game["score1"]:
            winner_line = f"🏆 برنده‌ی نهایی: {game['player2_name']}!"
        else:
            winner_line = "🤝 بازی مساوی تموم شد!"

        await query.edit_message_text(
            f"{result_line}\n\n"
            f"✂️📄🪨 نتیجه‌ی نهایی (۳ راند)\n"
            f"{game['player1_name']} {game['score1']} - {game['score2']} {game['player2_name']}\n\n"
            f"{winner_line}"
        )
        context.chat_data["rps_game"] = None
        return

    game["round"] += 1
    await query.edit_message_text(_round_text(game, extra=result_line), reply_markup=_rps_keyboard())
