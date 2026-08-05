# -*- coding: utf-8 -*-
"""
دستور «رمز ارز»: قیمت لحظه‌ای رمزارزها از API نوبیتکس، به‌صورت عکس.
هر عضو می‌تونه اسم یه رمزارز، دلار یا طلا رو تنها بنویسه تا فقط قیمت همون یکی رو ببینه.

نکته: نوبیتکس یک صرافی رمزارز است و قیمت طلا/دلار را پوشش نمی‌دهد،
برای همین این دو مورد از یک منبع عمومی دیگر (tgju) گرفته می‌شوند.
"""

import io
import os
import requests
from PIL import Image, ImageDraw, ImageFont

from telegram import Update
from telegram.ext import ContextTypes

NOBITEX_STATS_URL = "https://api.nobitex.ir/market/stats"
TGJU_URL = "https://call4.tgju.org/ajax.json"

# دلار و طلا از نوبیتکس در دسترس نیستن (نوبیتکس فقط رمزارزه)، برای همین از منبع دیگه‌ای می‌گیریم
FIAT_GOLD_MAP = {
    "دلار": ("price_dollar_rl", "💵"),
    "طلا": ("geram18", "🥇"),
}

# اسم فارسی -> (کد نماد در نوبیتکس, ایموجی)
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

FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "DejaVuSans-Bold.ttf")


def _get_font(size):
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


def _fa(text: str) -> str:
    return text


def fetch_all_stats():
    resp = requests.get(NOBITEX_STATS_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("stats", {})


def get_price_toman(stats: dict, symbol: str):
    """قیمت یک رمزارز به تومان + درصد تغییر امروز رو برمی‌گردونه، یا None اگه پیدا نشد"""
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
    resp = requests.get(TGJU_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("current", {})


def get_fiat_gold_price(tgju_data: dict, key: str):
    """قیمت دلار/طلا به تومان + درصد تغییر رو برمی‌گردونه، یا None اگه پیدا نشد"""
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


def _card_color(day_change):
    try:
        if day_change is not None and float(day_change) < 0:
            return (255, 90, 90)  # قرمز برای منفی
    except (TypeError, ValueError):
        pass
    return (90, 200, 130)  # سبز برای مثبت یا نامشخص


def render_grid_image(rows: list) -> Image.Image:
    """rows: لیستی از (نام فارسی, ایموجی, قیمت تومان, درصد تغییر)"""
    cols = 3
    card_w, card_h = 300, 140
    padding = 16
    n = len(rows)
    grid_rows = (n + cols - 1) // cols

    width = cols * card_w + (cols + 1) * padding
    height = grid_rows * card_h + (grid_rows + 1) * padding + 80

    img = Image.new("RGB", (width, height), (20, 20, 28))
    draw = ImageDraw.Draw(img)

    title_font = _get_font(34)
    name_font = _get_font(24)
    price_font = _get_font(26)
    change_font = _get_font(18)

    title = _fa("نرخ لحظه‌ای رمزارزها")
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, 20), title, font=title_font, fill=(255, 255, 255))

    for i, (name, emoji, price, change) in enumerate(rows):
        r, c = divmod(i, cols)
        x = padding + c * (card_w + padding)
        y = 80 + padding + r * (card_h + padding)

        color = _card_color(change)
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=18, fill=(32, 32, 44))
        draw.rounded_rectangle([x, y, x + 8, y + card_h], radius=4, fill=color)

        name_text = _fa(name)
        draw.text((x + 24, y + 16), name_text, font=name_font, fill=(255, 255, 255))

        price_text = _fa(f"{price:,} تومان") if price is not None else _fa("نامشخص")
        draw.text((x + 24, y + 58), price_text, font=price_font, fill=(255, 210, 90))

        if change is not None:
            try:
                change_val = float(change)
                sign = "+" if change_val >= 0 else ""
                change_text = f"{sign}{change_val:.2f}%"
                draw.text((x + 24, y + 98), change_text, font=change_font, fill=color)
            except (TypeError, ValueError):
                pass

    return img


def render_single_card(name: str, emoji: str, price, change) -> Image.Image:
    width, height = 700, 320
    img = Image.new("RGB", (width, height), (20, 20, 28))
    draw = ImageDraw.Draw(img)

    name_font = _get_font(40)
    price_font = _get_font(52)
    change_font = _get_font(26)
    label_font = _get_font(20)

    color = _card_color(change)
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=24, fill=(32, 32, 44), outline=color, width=4)

    name_text = _fa(name)
    nw = draw.textlength(name_text, font=name_font)
    draw.text(((width - nw) / 2, 55), name_text, font=name_font, fill=(255, 255, 255))

    price_text = _fa(f"{price:,} تومان") if price is not None else _fa("نامشخص")
    pw = draw.textlength(price_text, font=price_font)
    draw.text(((width - pw) / 2, 140), price_text, font=price_font, fill=(255, 210, 90))

    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            change_text = f"{sign}{change_val:.2f}% {_fa('تغییر امروز')}"
            cw = draw.textlength(change_text, font=change_font)
            draw.text(((width - cw) / 2, 220), change_text, font=change_font, fill=color)
        except (TypeError, ValueError):
            pass

    return img


def _image_to_bytes(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "price.png"
    return buf


async def cmd_crypto_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats = fetch_all_stats()
    except Exception as e:
        await update.effective_message.reply_text(f"❌ نتونستم به نوبیتکس وصل بشم.\n{e}")
        return

    rows = []
    for name, (symbol, emoji) in SYMBOL_MAP.items():
        if name in ("بیت‌کوین",):  # از دو تا املای بیت‌کوین فقط یکی تو گرید بیاد
            continue
        price, change = get_price_toman(stats, symbol)
        rows.append((name, emoji, price, change))

    img = render_grid_image(rows)
    await update.effective_message.reply_photo(photo=_image_to_bytes(img))


async def cmd_crypto_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.effective_message.text or "").strip()

    if text in FIAT_GOLD_MAP:
        key, emoji = FIAT_GOLD_MAP[text]
        try:
            tgju_data = fetch_tgju_data()
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم قیمت {text} رو بگیرم.\n{e}")
            return
        price, change = get_fiat_gold_price(tgju_data, key)
        img = render_single_card(text, emoji, price, change)
        await update.effective_message.reply_photo(photo=_image_to_bytes(img))
        return

    match = SYMBOL_MAP.get(text)
    if not match:
        return
    symbol, emoji = match

    try:
        stats = fetch_all_stats()
    except Exception as e:
        await update.effective_message.reply_text(f"❌ نتونستم به نوبیتکس وصل بشم.\n{e}")
        return

    price, change = get_price_toman(stats, symbol)
    img = render_single_card(text, emoji, price, change)
    await update.effective_message.reply_photo(photo=_image_to_bytes(img))
