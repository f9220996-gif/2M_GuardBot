# -*- coding: utf-8 -*-
"""
ماژول رمزارزها - قیمت لحظه‌ای با افکت شیشه‌ای
"""

import requests
from telegram import Update
from telegram.ext import ContextTypes

from price_card import render_single_card, image_to_bytes

# ========== تنظیمات ==========
NOBITEX_STATS_URL = "https://api.nobitex.ir/market/stats"
TGJU_URL = "https://call4.tgju.org/ajax.json"

# ========== نگاشت رمزارزها ==========
SYMBOL_MAP = {
    "تتر": ("usdt", "💵"),
    "بیت کوین": ("btc", "🟠"),
    "بیت‌کوین": ("btc", "🟠"),
    "اتریوم": ("eth", "🔷"),
    "دوج": ("doge", "🐶"),
    "تون": ("ton", "💎"),
    "ریپل": ("xrp", "🌊"),
    "کاردانو": ("ada", "🔵"),
    "سولانا": ("sol", "🟣"),
    "بایننس": ("bnb", "🟡"),
    "شیبا": ("shib", "🐕"),
    "ترون": ("trx", "🔴"),
    "آوالانچ": ("avax", "❄️"),
    "پولکادات": ("dot", "⚫️"),
    "پالیگان": ("matic", "🟪"),
    "چین لینک": ("link", "🔗"),
    "یونی": ("uni", "🦄"),
    "کازماس": ("atom", "⚛️"),
    "لایت کوین": ("ltc", "⚪️"),
    "بیت کوین کش": ("bch", "🟢"),
}

FIAT_GOLD_MAP = {
    "دلار": ("price_dollar_rl", "💵"),
    "طلا": ("geram18", "🥇"),
}

# ========== توابع API ==========
def fetch_all_stats():
    """دریافت قیمت‌ها از نوبیتکس"""
    try:
        resp = requests.get(NOBITEX_STATS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("stats", {})
    except:
        return {}

def get_price_toman(stats: dict, symbol: str):
    """گرفتن قیمت یک رمزارز به تومان"""
    for key in (f"{symbol}-rls", f"{symbol}rls"):
        if key in stats:
            entry = stats[key]
            try:
                price_rial = float(entry.get("latest") or entry.get("mark") or 0)
                price_toman = int(price_rial / 10)
                day_change = entry.get("dayChange")
                return price_toman, day_change
            except (TypeError, ValueError):
                return None, None
    return None, None

def fetch_tgju_data():
    """دریافت قیمت دلار و طلا از tgju"""
    try:
        resp = requests.get(TGJU_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("current", {})
    except:
        return {}

def get_fiat_gold_price(tgju_data: dict, key: str):
    """گرفتن قیمت دلار/طلا"""
    entry = tgju_data.get(key)
    if not entry:
        return None, None
    try:
        price_str = str(entry.get("p", "")).replace(",", "")
        price_rial = float(price_str)
        price_toman = int(price_rial / 10)
    except (TypeError, ValueError):
        return None, None
    change = entry.get("dp") or entry.get("d")
    try:
        change = float(str(change).replace("%", "")) if change is not None else None
    except (TypeError, ValueError):
        change = None
    return price_toman, change

# ========== دستورات ==========
async def cmd_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /crypto [نام] - قیمت یک رمزارز"""
    if not context.args:
        await update.effective_message.reply_text(
            "❗ لطفاً نام رمزارز رو وارد کنید.\n"
            "مثال: /crypto بیت‌کوین\n"
            "برای دیدن لیست کامل: /cryptolist"
        )
        return
    
    text = " ".join(context.args).strip()
    
    # بررسی دلار و طلا
    if text in FIAT_GOLD_MAP:
        key, emoji = FIAT_GOLD_MAP[text]
        tgju_data = fetch_tgju_data()
        if not tgju_data:
            await update.effective_message.reply_text(f"❌ نتونستم قیمت {text} رو بگیرم.")
            return
        price, change = get_fiat_gold_price(tgju_data, key)
        img = render_single_card(text, emoji, price, change)
        await update.effective_message.reply_photo(photo=image_to_bytes(img))
        return
    
    # بررسی رمزارزها
    match = SYMBOL_MAP.get(text)
    if not match:
        # جستجوی جزئی
        suggestions = [name for name in SYMBOL_MAP.keys() if text in name and name != "بیت‌کوین"]
        if suggestions:
            await update.effective_message.reply_text(
                f"❗ رمزارز '{text}' پیدا نشد.\n"
                f"آیا منظورتون یکی از ایناست؟\n" + "\n".join(suggestions[:5])
            )
        else:
            await update.effective_message.reply_text(
                f"❗ رمزارز '{text}' پیدا نشد.\n"
                "برای دیدن لیست کامل از /cryptolist استفاده کنید."
            )
        return
    
    symbol, emoji = match
    stats = fetch_all_stats()
    if not stats:
        await update.effective_message.reply_text("❌ نتونستم به نوبیتکس وصل بشم.")
        return
    
    price, change = get_price_toman(stats, symbol)
    img = render_single_card(text, emoji, price, change)
    await update.effective_message.reply_photo(photo=image_to_bytes(img))

async def cmd_cryptolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /cryptolist - نمایش لیست رمزارزها"""
    text = "📊 لیست رمزارزهای قابل مشاهده:\n\n"
    for name, (symbol, emoji) in SYMBOL_MAP.items():
        if name != "بیت‌کوین":  # جلوگیری از دوبار نمایش
            text += f"{emoji} {name}\n"
    text += "\n💵 دلار\n🥇 طلا"
    await update.effective_message.reply_text(text)
