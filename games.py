# -*- coding: utf-8 -*-
"""
چند بازی کوچیک و فان برای وقت بیکاری در گروه:
تاس، شیر یا خط، سنگ‌کاغذقیچی، حدس عدد
"""

import random
from telegram import Update
from telegram.ext import ContextTypes


async def cmd_tas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پرتاب تاس واقعی تلگرام (انیمیشن دار)"""
    await update.effective_message.reply_dice(emoji="🎲")


async def cmd_shir_khat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["شیر 🦁", "خط 〰️"])
    await update.effective_message.reply_text(f"🪙 نتیجه: {result}")


async def cmd_sang_kaghaz_gheychi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choices = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}
    user_choice = context.args[0] if context.args else None

    if not user_choice or user_choice not in choices:
        await update.effective_message.reply_text(
            "برای بازی بنویس یکی از این‌ها:\n"
            "سنگ_کاغذ_قیچی سنگ\n"
            "سنگ_کاغذ_قیچی کاغذ\n"
            "سنگ_کاغذ_قیچی قیچی"
        )
        return

    bot_choice = random.choice(list(choices.keys()))

    if user_choice == bot_choice:
        result = "مساوی شدیم! 🤝"
    elif (
        (user_choice == "سنگ" and bot_choice == "قیچی") or
        (user_choice == "کاغذ" and bot_choice == "سنگ") or
        (user_choice == "قیچی" and bot_choice == "کاغذ")
    ):
        result = "بردی! 🎉"
    else:
        result = "باختی! 😅"

    await update.effective_message.reply_text(
        f"تو: {user_choice} {choices[user_choice]}\n"
        f"من: {bot_choice} {choices[bot_choice]}\n"
        f"{result}"
    )


async def cmd_hads_adad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازی حدس عدد بین ۱ تا ۱۰"""
    secret = random.randint(1, 10)
    context.chat_data["hads_adad_secret"] = secret
    await update.effective_message.reply_text(
        "🔢 یک عدد بین ۱ تا ۱۰ در ذهنم انتخاب کردم!\n"
        "با دستور «حدس [عدد]» حدس بزن. مثلا: حدس 7"
    )


async def cmd_hads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    secret = context.chat_data.get("hads_adad_secret")
    if secret is None:
        await update.effective_message.reply_text("اول با دستور «حدس_عدد» بازی رو شروع کن.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("یک عدد بین ۱ تا ۱۰ بنویس. مثلا: حدس 7")
        return

    guess = int(context.args[0])
    if guess == secret:
        await update.effective_message.reply_text(f"🎉 آفرین! درست حدس زدی، عدد {secret} بود.")
        del context.chat_data["hads_adad_secret"]
    elif guess < secret:
        await update.effective_message.reply_text("بزرگ‌تر بگو ⬆️")
    else:
        await update.effective_message.reply_text("کوچیک‌تر بگو ⬇️")
