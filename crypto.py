# -*- coding: utf-8 -*-
"""
دستور «رمز ارز»: قیمت لحظه‌ای بیت‌کوین/تتر/بیت‌کوین‌کش/دلار/یورو/طلا، به‌صورت عکس.
هر عضو می‌تونه اسم یکی از این‌ها رو تنها بنویسه تا فقط قیمت همون یکی رو ببینه.

نکته‌ی مهم درباره‌ی منبع داده:
قبلاً قیمت رمزارزها از API نوبیتکس گرفته می‌شد، ولی چون نوبیتکس اخیراً هدف
تحریم‌های مستقیم آمریکا قرار گرفته، سرورهای میزبانی خارج از ایران (مثل
Railway) دیگه نمی‌تونن بهش وصل بشن. برای همین قیمت رمزارزها الان از
CoinGecko (بین‌المللی، رایگان، بدون محدودیت جغرافیایی) گرفته می‌شه، با
نمودار ۷ روزه‌ی واقعی. دلار، یورو و طلا هنوز از tgju میان، ولی چون
tgju نمودار تاریخی نمی‌ده، کارتشون بدون نمودار می‌مونه.

نکته درباره‌ی کلید یورو تو tgju:
کلید 'price_eur' یه حدسه (چون نمی‌تونم مستقیم tgju رو تست کنم). اگه یورو
جواب نداد، پیام خطا دقیقاً می‌گه مشکل کجاست تا کلید درست رو پیدا کنیم.

نکته درباره‌ی فونت اعداد:
اگه فایل assets/Poppins-Bold.ttf وجود داشته باشه، اعداد قیمت و درصد باهاش
نوشته می‌شن؛ وگرنه از همون فونت پیش‌فرض استفاده می‌شه. متن فارسی همیشه
با Vazirmatn نوشته می‌شه.
"""

import io
import os
import math
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telegram import Update
from telegram.ext import ContextTypes

import arabic_reshaper
from bidi.algorithm import get_display

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
TGJU_URL = "https://call4.tgju.org/ajax.json"

USER_AGENT = "Mozilla/5.0 (compatible; TelegramBot/1.0; +https://core.telegram.org/bots)"

# دلار، یورو و طلا رمزارز نیستن، برای همین از یه منبع عمومی دیگه (tgju) میان
FIAT_GOLD_MAP = {
    "دلار": ("price_dollar_rl", "💵", "dollar"),
    "یورو": ("price_eur", "💶", "euro"),
    "طلا": ("geram18", "🥇", "gold"),
}

# اسم فارسی -> (نماد کوتاه, ایموجی) — فقط همین ۳ تا رمزارز
SYMBOL_MAP = {
    "تتر": ("usdt", "💵"),
    "بیت کوین": ("btc", "🟠"),
    "بیت‌کوین": ("btc", "🟠"),
    "بیت کوین کش": ("bch", "🟢"),
}

# نماد کوتاه -> آیدیِ همون کوین تو CoinGecko
COINGECKO_IDS = {
    "usdt": "tether",
    "btc": "bitcoin",
    "bch": "bitcoin-cash",
}

# نماد کوتاه -> بج (تیکر) که رو کارت نشون داده می‌شه
TICKERS = {
    "usdt": "USDT",
    "btc": "BTC",
    "bch": "BCH",
    "dollar": "USD",
    "euro": "EUR",
    "gold": "IRT",
}

# اسم هر مورد به زبان‌های دیگه (برای نمایش داخل عکس)
NAME_TRANSLATIONS = {
    "usdt": {"fa": "تتر", "en": "Tether", "ar": "تيثر"},
    "btc": {"fa": "بیت کوین", "en": "Bitcoin", "ar": "بيتكوين"},
    "bch": {"fa": "بیت کوین کش", "en": "Bitcoin Cash", "ar": "بيتكوين كاش"},
    "dollar": {"fa": "دلار آمریکا", "en": "US Dollar", "ar": "الدولار الأمريكي"},
    "euro": {"fa": "یورو", "en": "Euro", "ar": "اليورو"},
    "gold": {"fa": "طلا (۱۸ عیار)", "en": "Gold (18k)", "ar": "الذهب (18 قيراط)"},
}

FLAG_EMOJI = {
    "usdt": "💵",
    "btc": "🟠",
    "bch": "🟢",
    "dollar": "🇺🇸",
    "euro": "🇪🇺",
    "gold": "🥇",
}

# رنگ اختصاصیِ هر مورد - برای تینت‌کردن کارت‌های غیرِ پرچمی (طلا و رمزارزها)
COIN_COLORS = {
    "btc": (247, 147, 26),
    "usdt": (38, 161, 123),
    "bch": (139, 195, 74),
    "gold": (230, 175, 60),
}

# این دوتا کارتشون «پرچم» می‌شه، نه تینت تیره
FLAG_STYLE_SYMBOLS = {"dollar", "euro"}

UI_STRINGS = {
    "fa": {
        "greeting": "سلام جوان ایرانی", "price_label": "قیمت لحظه‌ای", "currency": "تومان",
        "change_suffix": "تغییر نسبت به دیروز", "updated": "بروزرسانی", "unknown": "نامشخص",
        "grid_title": "نرخ لحظه‌ای بازار", "grid_subtitle": "قدرت‌گرفته از CoinGecko",
    },
    "en": {
        "greeting": "Hello Iranian Youth", "price_label": "Live Price", "currency": "Toman",
        "change_suffix": "change vs yesterday", "updated": "Updated", "unknown": "N/A",
        "grid_title": "Live Market Rates", "grid_subtitle": "Powered by CoinGecko",
    },
    "ar": {
        "greeting": "مرحباً أيها الشاب الإيراني", "price_label": "السعر اللحظي", "currency": "تومان",
        "change_suffix": "التغيير مقارنة بالأمس", "updated": "آخر تحديث", "unknown": "غير معروف",
        "grid_title": "أسعار السوق اللحظية", "grid_subtitle": "مدعوم من CoinGecko",
    },
}

LANG_NAMES = {"fa": "فارسی", "en": "English", "ar": "العربية"}


def _tr_name(symbol, lang):
    entry = NAME_TRANSLATIONS.get(symbol)
    if not entry:
        return symbol
    return entry.get(lang, entry.get("fa", symbol))


def _ui(lang, key):
    return UI_STRINGS.get(lang, UI_STRINGS["fa"]).get(key, UI_STRINGS["fa"][key])


ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
FONT_PATH = os.path.join(ASSETS_DIR, "Vazirmatn-Bold.ttf")
FALLBACK_FONT_PATH = os.path.join(ASSETS_DIR, "DejaVuSans-Bold.ttf")
NUMBER_FONT_PATH = os.path.join(ASSETS_DIR, "Poppins-Bold.ttf")


def _get_font(size):
    """فونت متن فارسی (اسم‌ها، برچسب‌ها)"""
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    if os.path.exists(FALLBACK_FONT_PATH):
        return ImageFont.truetype(FALLBACK_FONT_PATH, size)
    return ImageFont.load_default()


def _get_number_font(size):
    """فونت اعداد (قیمت، درصد) - اگه Poppins-Bold.ttf تو assets باشه، همونه"""
    if os.path.exists(NUMBER_FONT_PATH):
        return ImageFont.truetype(NUMBER_FONT_PATH, size)
    return _get_font(size)


def _fa(text: str) -> str:
    """متن فارسی رو برای نمایش درست (حروف چسبیده + جهت راست‌به‌چپ) روی عکس آماده می‌کنه"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _coin_color(symbol):
    return COIN_COLORS.get(symbol, (147, 51, 234))


# ---------------------------------------------------------------------------
# دریافت داده: CoinGecko برای رمزارزها (با نمودار ۷ روزه)، tgju برای دلار/یورو/طلا
# ---------------------------------------------------------------------------

def fetch_coingecko_markets():
    ids = ",".join(sorted(set(COINGECKO_IDS.values())))
    params = {
        "vs_currency": "usd",
        "ids": ids,
        "sparkline": "true",
        "price_change_percentage": "24h",
    }
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(COINGECKO_MARKETS_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {item["id"]: item for item in data}


def get_price_toman(markets_data: dict, symbol: str, usd_to_toman):
    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id:
        return None, None, None
    entry = markets_data.get(cg_id)
    if not entry:
        return None, None, None

    usd_price = entry.get("current_price")
    change = entry.get("price_change_percentage_24h")
    sparkline = None
    sp = entry.get("sparkline_in_7d") or {}
    if sp.get("price"):
        sparkline = sp["price"]

    if usd_price is None or usd_to_toman is None:
        return None, change, sparkline
    try:
        price_toman = int(float(usd_price) * float(usd_to_toman))
    except (TypeError, ValueError):
        return None, change, sparkline
    return price_toman, change, sparkline


def fetch_tgju_data():
    resp = requests.get(TGJU_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("current", {})


def get_fiat_gold_price(tgju_data: dict, key: str):
    """قیمت دلار/یورو/طلا به تومان + درصد تغییر رو برمی‌گردونه، یا None اگه پیدا نشد"""
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


def get_usd_to_toman_rate(tgju_data: dict):
    rate, _ = get_fiat_gold_price(tgju_data, "price_dollar_rl")
    return rate


# ---------------------------------------------------------------------------
# پس‌زمینه‌ی کلیِ عکس (پشت همه‌ی کارت‌ها)
# ---------------------------------------------------------------------------

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


BG_IMAGE_PATH = os.path.join(ASSETS_DIR, "price_card_bg.jpg")


def _load_background(width, height, blur=3, darken=120):
    if not os.path.exists(BG_IMAGE_PATH):
        return _vertical_gradient(width, height, (24, 14, 40), (10, 6, 18))

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
        top = (src_h - new_h) // 3
        bg = bg.crop((0, top, src_w, top + new_h))
    bg = bg.resize((width, height), Image.LANCZOS)

    if blur:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))

    overlay = Image.new("RGBA", (width, height), (8, 4, 18, darken))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    return bg


# ---------------------------------------------------------------------------
# پرچم‌های رسم‌شده با کد (نه عکس دانلودی) - فقط برای دلار و یورو
# ---------------------------------------------------------------------------

def _make_flag_image(kind, w, h):
    w, h = max(1, int(w)), max(1, int(h))
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    if kind == "dollar":
        stripes = 13
        stripe_h = h / stripes
        for i in range(stripes):
            color = (178, 34, 52) if i % 2 == 0 else (255, 255, 255)
            draw.rectangle([0, i * stripe_h, w, (i + 1) * stripe_h], fill=color)
        canton_w, canton_h = w * 0.4, h * 7 / 13
        draw.rectangle([0, 0, canton_w, canton_h], fill=(60, 59, 110))
        # چندتا نقطه‌ی ساده به‌جای ستاره‌های دقیق، فقط برای حس پرچم
        rows, cols = 5, 6
        for rr in range(rows):
            for cc in range(cols):
                sx = canton_w * (cc + 0.5) / cols
                sy = canton_h * (rr + 0.5) / rows
                r = min(canton_w, canton_h) * 0.035
                draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 255, 255))

    elif kind == "euro":
        draw.rectangle([0, 0, w, h], fill=(0, 51, 153))
        cx, cy = w / 2, h / 2
        R = min(w, h) * 0.30
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            sx, sy = cx + R * math.cos(angle), cy + R * math.sin(angle)
            r = min(w, h) * 0.032
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 204, 0))

    return img


def _draw_sparkline(img: Image.Image, x0, y0, x1, y1, prices, up: bool):
    """یه نمودار ناحیه‌ای (area chart) ساده از لیست قیمت‌ها می‌کشه"""
    if not prices or len(prices) < 2:
        return img
    w = x1 - x0
    h = y1 - y0
    lo, hi = min(prices), max(prices)
    rng = (hi - lo) or (hi * 0.01 or 1)
    n = len(prices)

    pts = []
    for i, p in enumerate(prices):
        px = x0 + (i / (n - 1)) * w
        py = y1 - ((p - lo) / rng) * h
        pts.append((px, py))

    color = (96, 210, 140) if up else (230, 95, 95)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    poly = pts + [(x1, y1), (x0, y1)]
    odraw.polygon(poly, fill=(*color, 55))
    odraw.line(pts, fill=(*color, 255), width=3, joint="curve")

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _draw_price_card(img, x, y, w, h, symbol, badge_text, title_text, price, currency_word, unknown_word,
                      change, sparkline=None, big=False):
    """
    اگه symbol جزو FLAG_STYLE_SYMBOLS باشه (دلار/یورو): پس‌زمینه‌ی کارت
    پرچمِ همون کشور می‌شه و یه کارت روشن داخلش برای متن می‌ذاریم (مثل نمونه).
    وگرنه (طلا/رمزارزها): همون کارت تیره‌ی تینت‌شده‌ی قبلی.
    """
    is_flag = symbol in FLAG_STYLE_SYMBOLS

    if is_flag:
        flag_img = _make_flag_image(symbol, w, h)
        mask = Image.new("L", (int(w), int(h)), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle([0, 0, int(w) - 1, int(h) - 1], radius=26, fill=255)
        img = img.copy()
        img.paste(flag_img, (int(x), int(y)), mask)

        inner_pad = 22
        ix0, iy0 = x + inner_pad, y + inner_pad
        ix1, iy1 = x + w - inner_pad, y + h - inner_pad

        light_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ldraw = ImageDraw.Draw(light_layer)
        ldraw.rounded_rectangle([ix0, iy0, ix1, iy1], radius=20, fill=(250, 250, 252, 240))
        img = Image.alpha_composite(img.convert("RGBA"), light_layer).convert("RGB")

        x, y, w, h = ix0, iy0, ix1 - ix0, iy1 - iy0
        title_color = (30, 30, 40)
        price_color = (20, 20, 30)
        badge_bg = (235, 235, 240, 255)
        badge_fg = (60, 60, 70)
    else:
        accent = _coin_color(symbol)
        base = (14, 11, 24)
        tinted = tuple(int(a * 0.22 + b * 0.78) for a, b in zip(accent, base))

        card_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card_layer)
        cdraw.rounded_rectangle([x, y, x + w, y + h], radius=26, fill=(*tinted, 235))
        cdraw.rounded_rectangle([x, y, x + w, y + h], radius=26, outline=(*accent, 160), width=2)
        img = Image.alpha_composite(img.convert("RGBA"), card_layer).convert("RGB")

        title_color = (255, 255, 255)
        price_color = (255, 215, 110)
        badge_bg = (255, 255, 255, 28)
        badge_fg = (235, 230, 245)

    draw = ImageDraw.Draw(img)
    pad = 24 if big else 18
    badge_font = _get_font(22 if big else 17)
    title_font = _get_font(30 if big else 21)
    price_font = _get_number_font(58 if big else 34)
    change_font = _get_number_font(22 if big else 16)

    # ===== بج بالا-چپ (تیکر) =====
    bw = draw.textlength(badge_text, font=badge_font) + 24
    bh = 38 if big else 28
    draw.rounded_rectangle([x + pad, y + pad, x + pad + bw, y + pad + bh], radius=bh / 2, fill=badge_bg)
    draw.text((x + pad + 12, y + pad + bh / 2 - (badge_font.size / 2) - 2), badge_text, font=badge_font, fill=badge_fg)

    # ===== عنوان بالا-راست =====
    title_disp = _fa(title_text)
    tw = draw.textlength(title_disp, font=title_font)
    draw.text((x + w - pad - tw, y + pad + (bh - title_font.size) / 2 - 2), title_disp, font=title_font, fill=title_color)

    # ===== قیمت بزرگ (عدد با فونت لاتین، «تومان» با فونت فارسی - جدا از هم) =====
    price_y = y + pad + bh + (26 if big else 16)
    price_h = 0
    if price is not None:
        num_str = f"{price:,}"
        draw.text((x + pad, price_y), num_str, font=price_font, fill=price_color)
        num_w = draw.textlength(num_str, font=price_font)
        currency_font = _get_font(int(price_font.size * 0.42))
        currency_disp = _fa(currency_word)
        draw.text(
            (x + pad + num_w + 12, price_y + price_font.size - currency_font.size - 4),
            currency_disp, font=currency_font, fill=price_color
        )
        price_h = price_font.size
    else:
        unknown_font = _get_font(int(price_font.size * 0.55))
        unknown_disp = _fa(unknown_word)
        draw.text((x + pad, price_y), unknown_disp, font=unknown_font, fill=price_color)
        price_h = unknown_font.size

    # ===== پیل رنگیِ درصد تغییر (با یه مثلث رسم‌شده، نه کاراکتر فلش) =====
    up = True
    chip_y = price_y + price_h + (14 if big else 8)
    if change is not None:
        try:
            change_val = float(change)
            up = change_val >= 0
            sign = "+" if up else ""
            chg_text = f"{sign}{change_val:.2f}%"
            chg_color = (40, 150, 85) if up else (195, 60, 60)
            tri_w = 12
            cw = draw.textlength(chg_text, font=change_font) + tri_w + 32
            ch = change_font.size + 16
            draw.rounded_rectangle([x + pad, chip_y, x + pad + cw, chip_y + ch], radius=ch / 2, fill=chg_color)

            # مثلثِ رو به بالا (سبز) یا رو به پایین (قرمز)، به‌جای کاراکتر ▲/▼
            tri_cx = x + pad + 16
            tri_cy = chip_y + ch / 2
            if up:
                tri = [(tri_cx, tri_cy - 6), (tri_cx - 6, tri_cy + 5), (tri_cx + 6, tri_cy + 5)]
            else:
                tri = [(tri_cx, tri_cy + 6), (tri_cx - 6, tri_cy - 5), (tri_cx + 6, tri_cy - 5)]
            draw.polygon(tri, fill=(255, 255, 255))

            draw.text((x + pad + tri_w + 20, chip_y + 8), chg_text, font=change_font, fill=(255, 255, 255))
            chip_y += ch
        except (TypeError, ValueError):
            pass

    # ===== نمودار ۷ روزه (فقط رمزارزها، چون دلار/یورو/طلا نمودار ندارن) =====
    if sparkline and len(sparkline) > 1:
        chart_x0 = x + pad
        chart_x1 = x + w - pad
        chart_y1 = y + h - (pad - 4)
        chart_top_limit = chip_y + 10
        chart_h = max(30, chart_y1 - chart_top_limit)
        chart_y0 = chart_y1 - chart_h
        img = _draw_sparkline(img, chart_x0, chart_y0, chart_x1, chart_y1, sparkline, up)

    return img


def _image_to_bytes(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "price.png"
    return buf


# ---------------------------------------------------------------------------
# ساخت عکسِ نهایی (چه تکی، چه گرید)
# ---------------------------------------------------------------------------

def render_single_card(symbol: str, price, change, lang: str = "fa", sparkline=None) -> Image.Image:
    width, height = 1200, 675  # نسبت دقیق 16:9
    img = _load_background(width, height)

    name = _tr_name(symbol, lang)
    title_text = name
    badge_text = TICKERS.get(symbol, symbol.upper())
    currency = _ui(lang, "currency")
    unknown = _ui(lang, "unknown")

    card_margin = 60
    img = _draw_price_card(
        img, card_margin, card_margin,
        width - 2 * card_margin, height - 2 * card_margin,
        symbol, badge_text, title_text, price, currency, unknown, change, sparkline=sparkline, big=True
    )

    draw = ImageDraw.Draw(img)
    footer_font = _get_font(18)
    from persian_date import format_persian_datetime
    footer_text = _fa(f"{_ui(lang, 'updated')}: {format_persian_datetime()}")
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) / 2, height - 34), footer_text, font=footer_font, fill=(210, 200, 220))

    return img


def render_grid_image(items: list, lang: str = "fa") -> Image.Image:
    """items: لیستی از دیکشنری {"symbol":, "price":, "change":, "sparkline":}"""
    width, height = 1600, 900
    img = _load_background(width, height)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(38)
    sub_font = _get_font(20)

    title = _fa(_ui(lang, "grid_title"))
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, 34), title, font=title_font, fill=(255, 255, 255))

    sub = _fa(_ui(lang, "grid_subtitle"))
    sw = draw.textlength(sub, font=sub_font)
    draw.text(((width - sw) / 2, 82), sub, font=sub_font, fill=(215, 205, 230))

    n = len(items)
    cols = 3 if n > 2 else n
    grid_rows = (n + cols - 1) // cols

    margin = 40
    top = 130
    gap = 22
    available_w = width - 2 * margin
    available_h = height - top - margin

    card_w = (available_w - (cols - 1) * gap) / cols
    card_h = (available_h - (grid_rows - 1) * gap) / grid_rows

    for i, item in enumerate(items):
        symbol = item["symbol"]
        price = item["price"]
        change = item["change"]
        sparkline = item.get("sparkline")

        r, c = divmod(i, cols)
        x = margin + c * (card_w + gap)
        y = top + r * (card_h + gap)

        name = _tr_name(symbol, lang)
        title_text = name
        badge_text = TICKERS.get(symbol, symbol.upper())
        currency = _ui(lang, "currency")
        unknown = _ui(lang, "unknown")

        img = _draw_price_card(img, x, y, card_w, card_h, symbol, badge_text, title_text, price, currency, unknown, change, sparkline=sparkline)

    return img


def _build_caption(symbol, price, change, lang="fa"):
    name = _tr_name(symbol, lang)
    currency = _ui(lang, "currency")
    if price is None:
        price_str = _ui(lang, "unknown")
    else:
        price_str = f"{price:,} {currency}"

    if lang == "en":
        text = f"{name} today: {price_str}"
    elif lang == "ar":
        text = f"{name} اليوم: {price_str}"
    else:
        text = f"{name} امروز {price_str}"

    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            text += f" ({sign}{change_val:.2f}٪)"
        except (TypeError, ValueError):
            pass
    return text


# ---------------------------------------------------------------------------
# دستورها
# ---------------------------------------------------------------------------

async def cmd_crypto_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import database as db
    chat = update.effective_chat
    lang = db.get_image_lang(chat.id) if chat and chat.type in ("group", "supergroup") else "fa"

    try:
        try:
            tgju_data = fetch_tgju_data()
            usd_toman = get_usd_to_toman_rate(tgju_data)
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم نرخ دلار رو بگیرم (لازم برای تبدیل قیمت‌ها به تومان).\n{e}")
            return

        try:
            cg_data = fetch_coingecko_markets()
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم به CoinGecko وصل بشم.\n{e}")
            return

        items = []

        seen_symbols = set()
        for name, (symbol, emoji) in SYMBOL_MAP.items():
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            price, change, sparkline = get_price_toman(cg_data, symbol, usd_toman)
            items.append({"symbol": symbol, "price": price, "change": change, "sparkline": sparkline})

        for name, (key, emoji, trans_key) in FIAT_GOLD_MAP.items():
            price, change = get_fiat_gold_price(tgju_data, key)
            items.append({"symbol": trans_key, "price": price, "change": change, "sparkline": None})

        img = render_grid_image(items, lang=lang)
        from persian_date import format_persian_datetime
        caption = f"{_ui(lang, 'grid_title')} — {_ui(lang, 'updated')}: {format_persian_datetime()}"
        await update.effective_message.reply_photo(photo=_image_to_bytes(img), caption=caption)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ خطای غیرمنتظره تو ساختن جدول قیمت‌ها.\n{e}")


async def cmd_crypto_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import database as db
    text = (update.effective_message.text or "").strip()
    chat = update.effective_chat
    lang = db.get_image_lang(chat.id) if chat and chat.type in ("group", "supergroup") else "fa"

    if text in FIAT_GOLD_MAP:
        key, emoji, trans_key = FIAT_GOLD_MAP[text]
        try:
            tgju_data = fetch_tgju_data()
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم قیمت {text} رو بگیرم.\n{e}")
            return
        price, change = get_fiat_gold_price(tgju_data, key)
        if price is None:
            await update.effective_message.reply_text(
                f"❌ نتونستم قیمت {text} رو پیدا کنم. (کلید '{key}' تو دیتای tgju پیدا نشد؛ ممکنه اسم کلید عوض شده باشه.)"
            )
            return
        img = render_single_card(trans_key, price, change, lang=lang, sparkline=None)
        caption = _build_caption(trans_key, price, change, lang=lang)
        await update.effective_message.reply_photo(photo=_image_to_bytes(img), caption=caption)
        return

    match = SYMBOL_MAP.get(text)
    if not match:
        return
    symbol, emoji = match

    try:
        try:
            tgju_data = fetch_tgju_data()
            usd_toman = get_usd_to_toman_rate(tgju_data)
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم نرخ دلار رو بگیرم (لازم برای تبدیل قیمت به تومان).\n{e}")
            return

        try:
            cg_data = fetch_coingecko_markets()
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم به CoinGecko وصل بشم.\n{e}")
            return

        price, change, sparkline = get_price_toman(cg_data, symbol, usd_toman)
        img = render_single_card(symbol, price, change, lang=lang, sparkline=sparkline)
        caption = _build_caption(symbol, price, change, lang=lang)
        await update.effective_message.reply_photo(photo=_image_to_bytes(img), caption=caption)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ خطای غیرمنتظره تو ساختن قیمت {text}.\n{e}")
