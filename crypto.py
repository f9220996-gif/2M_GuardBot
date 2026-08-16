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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telegram import Update
from telegram.ext import ContextTypes

import arabic_reshaper
from bidi.algorithm import get_display

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

FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "Vazirmatn-Bold.ttf")
FALLBACK_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "DejaVuSans-Bold.ttf")


def _get_font(size):
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    if os.path.exists(FALLBACK_FONT_PATH):
        return ImageFont.truetype(FALLBACK_FONT_PATH, size)
    return ImageFont.load_default()


def _fa(text: str) -> str:
    """متن فارسی رو برای نمایش درست (حروف چسبیده + جهت راست‌به‌چپ) روی عکس آماده می‌کنه"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


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


COIN_COLORS = {
    "btc": (247, 147, 26),
    "eth": (98, 126, 234),
    "usdt": (38, 161, 123),
    "doge": (194, 163, 76),
    "ton": (0, 152, 234),
    "xrp": (35, 41, 47),
    "ada": (14, 116, 224),
    "sol": (153, 69, 255),
    "bnb": (240, 185, 11),
    "shib": (255, 92, 0),
    "trx": (235, 12, 12),
    "avax": (232, 65, 66),
    "dot": (230, 0, 122),
    "matic": (130, 71, 229),
    "link": (42, 91, 220),
    "uni": (255, 0, 122),
    "atom": (46, 58, 91),
    "ltc": (166, 166, 166),
    "bch": (139, 195, 74),
}


def _coin_color(symbol):
    return COIN_COLORS.get(symbol, (147, 51, 234))


def render_grid_image(rows: list) -> Image.Image:
    """rows: لیستی از (نام فارسی, نماد نوبیتکس, قیمت تومان, درصد تغییر)"""
    cols = 2
    card_w, card_h = 460, 150
    padding = 20
    n = len(rows)
    grid_rows = (n + cols - 1) // cols

    width = cols * card_w + (cols + 1) * padding
    height = grid_rows * card_h + (grid_rows + 1) * padding + 120

    img = Image.new("RGB", (width, height), (14, 14, 20))
    draw = ImageDraw.Draw(img)

    # نوار سرصفحه با گرادیان بنفش ساده
    for i in range(100):
        t = i / 100
        r = int(88 + (147 - 88) * t)
        g = int(28 + (51 - 28) * t)
        b = int(150 + (234 - 150) * t)
        draw.line([(0, i), (width, i)], fill=(r, g, b))

    title_font = _get_font(38)
    sub_font = _get_font(20)
    name_font = _get_font(26)
    price_font = _get_font(30)
    change_font = _get_font(20)
    icon_font = _get_font(28)

    title = _fa("نرخ لحظه‌ای رمزارزها")
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, 22), title, font=title_font, fill=(255, 255, 255))

    sub = _fa("قدرت‌گرفته از نوبیتکس")
    sw = draw.textlength(sub, font=sub_font)
    draw.text(((width - sw) / 2, 70), sub, font=sub_font, fill=(255, 255, 255))

    for i, (name, symbol, price, change) in enumerate(rows):
        r, c = divmod(i, cols)
        x = padding + c * (card_w + padding)
        y = 120 + padding + r * (card_h + padding)

        accent = _coin_color(symbol)
        change_color = _card_color(change)

        # پس‌زمینه کارت با یه سایه‌ی ملایم از رنگ خود ارز
        shade = tuple(int(a * 0.10 + b * 0.90) for a, b in zip(accent, (24, 24, 32)))
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=22, fill=shade, outline=accent, width=3)

        # آیکون دایره‌ای رنگی با حرف اول نماد
        icon_r = 28
        icon_cx, icon_cy = x + card_w - 24 - icon_r, y + card_h / 2
        draw.ellipse(
            [icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r],
            fill=accent
        )
        letter = symbol[0].upper()
        lw = draw.textlength(letter, font=icon_font)
        draw.text((icon_cx - lw / 2, icon_cy - 16), letter, font=icon_font, fill=(255, 255, 255))

        name_text = _fa(name)
        draw.text((x + 24, y + 20), name_text, font=name_font, fill=(255, 255, 255))

        price_text = _fa(f"{price:,} تومان") if price is not None else _fa("نامشخص")
        draw.text((x + 24, y + 62), price_text, font=price_font, fill=(255, 210, 90))

        if change is not None:
            try:
                change_val = float(change)
                sign = "+" if change_val >= 0 else ""
                change_text = f"{sign}{change_val:.2f}%"
                draw.text((x + 24, y + 108), change_text, font=change_font, fill=change_color)
            except (TypeError, ValueError):
                pass

    return img


def _vertical_gradient(width, height, top_color, bottom_color):
    img = Image.new("RGB", (width, height), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _add_glow(img, cx, cy, radius, color, intensity=90):
    """یه هاله‌ی نوری تار (glow) پشت صحنه اضافه می‌کنه"""
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_layer)
    gdraw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, intensity))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius / 2))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow_layer).convert("RGB"), (0, 0))
    return img


def _draw_floor_grid(draw, width, height, top_y, color=(90, 60, 140), lines=8):
    """یه شبکه‌ی خطوط رو به پایین (حس کف براق) برای تزئین گوشه‌ها می‌کشه"""
    for i in range(lines + 1):
        x = width * i / lines
        draw.line([(x, height), (width / 2 + (x - width / 2) * 0.15, top_y)], fill=color, width=1)
    for i in range(4):
        t = i / 3
        y = top_y + (height - top_y) * t
        shrink = (1 - t) * 0.42
        draw.line([(width * shrink, y), (width * (1 - shrink), y)], fill=color, width=1)


def _draw_candles(draw, x0, y0, width, height, up_color=(90, 200, 130), down_color=(230, 90, 90)):
    """چند تا کندل‌استیک کوچیک تزئینی (شبیه نمودار بورس) می‌کشه"""
    import random
    rnd = random.Random(7)  # سید ثابت تا هر بار یه شکل ثابت و قشنگ بکشه
    n = 10
    cw = width / (n * 1.6)
    x = x0
    prev = y0 + height * 0.55
    for i in range(n):
        body_h = rnd.randint(int(height * 0.06), int(height * 0.22))
        up = rnd.random() > 0.42
        color = up_color if up else down_color
        top = prev - body_h if up else prev
        bottom = prev if up else prev + body_h
        wick = rnd.randint(6, 22)
        draw.line([(x + cw / 2, top - wick), (x + cw / 2, bottom + wick)], fill=color, width=2)
        draw.rectangle([x, top, x + cw, bottom], fill=color)
        prev = top if up else bottom
        prev += rnd.randint(-10, 10)
        x += cw * 1.6


def _draw_corner_ornaments(draw, x0, y0, x1, y1, color, size=26):
    """چهار خط تزئینی گوشه‌ی کادر، برای حس شیک‌تر بدون نیاز به فونت خاص"""
    for (cx, cy, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        draw.line([(cx, cy), (cx + size * dx, cy)], fill=color, width=4)
        draw.line([(cx, cy), (cx, cy + size * dy)], fill=color, width=4)


BG_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "price_card_bg.jpg")


def _load_background(width, height):
    """پس‌زمینه واقعی رو می‌گیره، برش می‌زنه که کامل قاب رو پر کنه، و کمی تیره‌ترش می‌کنه"""
    if not os.path.exists(BG_IMAGE_PATH):
        return _vertical_gradient(width, height, (18, 10, 34), (6, 4, 14))

    bg = Image.open(BG_IMAGE_PATH).convert("RGB")
    src_w, src_h = bg.size
    target_ratio = width / height
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        bg = bg.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 3  # کمی از بالا برش بخوره که کوین‌ها بمونن
        bg = bg.crop((0, top, src_w, top + new_h))
    bg = bg.resize((width, height), Image.LANCZOS)

    # یه لایه تیره‌ی نیمه‌شفاف رو کل عکس، که متن روش خواناتر بشه
    overlay = Image.new("RGBA", (width, height), (8, 4, 18, 110))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    return bg


def _glass_panel(img, x0, y0, x1, y1, radius=28, fill_alpha=150, border_color=(200, 170, 255, 90)):
    """یه پنل شیشه‌ای نیمه‌شفاف با خط دور ظریف و نورانی، به‌جای کادر ضخیم قبلی"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layer)
    ldraw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=(20, 14, 34, fill_alpha))
    ldraw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_color, width=2)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def render_single_card(name: str, emoji: str, price, change, extra_info=None) -> Image.Image:
    width, height = 1000, 620
    gold = (255, 200, 70)

    img = _load_background(width, height)

    # پنل شیشه‌ای پشت متن‌ها (به‌جای کادر ضخیم بنفش قبلی)
    panel_margin = 70
    img = _glass_panel(img, panel_margin, panel_margin, width - panel_margin, height - panel_margin)
    draw = ImageDraw.Draw(img)
    _draw_corner_ornaments(draw, panel_margin + 20, panel_margin + 20, width - panel_margin - 20, height - panel_margin - 20, gold, size=26)

    greeting_font = _get_font(24)
    name_font = _get_font(54)
    price_label_font = _get_font(24)
    price_font = _get_font(72)
    change_font = _get_font(30)
    footer_font = _get_font(20)
    detail_font = _get_font(22)

    # خط باریک تزئینی بالای عنوان
    draw.line([(width / 2 - 60, 108), (width / 2 + 60, 108)], fill=gold, width=3)

    greeting_text = _fa("سلام جوان ایرانی")
    gw = draw.textlength(greeting_text, font=greeting_font)
    draw.text(((width - gw) / 2, 118), greeting_text, font=greeting_font, fill=(210, 200, 225))

    name_text = _fa(name)
    nw = draw.textlength(name_text, font=name_font)
    draw.text(((width - nw) / 2, 168), name_text, font=name_font, fill=(255, 255, 255))

    # خط جداکننده
    draw.line([(160, 250), (width - 160, 250)], fill=(140, 110, 180), width=1)

    price_label = _fa("قیمت لحظه‌ای")
    plw = draw.textlength(price_label, font=price_label_font)
    draw.text(((width - plw) / 2, 272), price_label, font=price_label_font, fill=(200, 190, 215))

    price_text = _fa(f"{price:,} تومان") if price is not None else _fa("نامشخص")
    pw = draw.textlength(price_text, font=price_font)
    draw.text(((width - pw) / 2, 306), price_text, font=price_font, fill=gold)

    y_cursor = 400
    color = _card_color(change)
    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            change_text = _fa(f"{sign}{change_val:.2f}٪ تغییر نسبت به دیروز")
            cw = draw.textlength(change_text, font=change_font)
            draw.text(((width - cw) / 2, y_cursor), change_text, font=change_font, fill=color)
            y_cursor += 48
        except (TypeError, ValueError):
            pass

    if extra_info:
        for line in extra_info:
            line_text = _fa(line)
            lw = draw.textlength(line_text, font=detail_font)
            draw.text(((width - lw) / 2, y_cursor), line_text, font=detail_font, fill=(210, 205, 220))
            y_cursor += 34

    from persian_date import format_persian_datetime
    footer_text = _fa(f"بروزرسانی: {format_persian_datetime()}")
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) / 2, height - panel_margin - 44), footer_text, font=footer_font, fill=(190, 180, 205))

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
        rows.append((name, symbol, price, change))

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
