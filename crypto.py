# -*- coding: utf-8 -*-
"""
دستورهای «دلار»، «طلا» و «تتر»: قیمت لحظه‌ای هرکدوم، جدا از هم، به‌صورت عکس یا ویدیو.
هر عضو اسم یکی از این‌ها رو می‌نویسه و فقط قیمت همون یکی رو می‌بینه.
هیچ جدول/گرید ترکیبی‌ای وجود نداره - هر سه کاملاً مستقل از هم کار می‌کنن.

نکته‌ی مهم درباره‌ی منبع داده:
قبلاً قیمت رمزارزها از API نوبیتکس گرفته می‌شد، ولی چون نوبیتکس اخیراً هدف
تحریم‌های مستقیم آمریکا قرار گرفته، سرورهای میزبانی خارج از ایران (مثل
Railway) دیگه نمی‌تونن بهش وصل بشن. برای همین قیمت تتر از CoinGecko
(بین‌المللی، رایگان، بدون محدودیت جغرافیایی) گرفته می‌شه. دلار و طلا
مستقیماً از tgju میان.

نکته‌ی مهم درباره‌ی ویدیو:
وقتی assets/price_card_bg.mp4 وجود داشته باشه، به‌جای عکس، یک PNG شفاف
شامل پنل+متن قیمت ساخته می‌شه و با ffmpeg روی فریم‌های ویدیو overlay
می‌شه (burn-in). چون قیمت هر بار عوض می‌شه، دیگه file_id ویدیو کش
نمی‌شه - هر درخواست، ویدیوی تازه با قیمت لحظه‌ای ساخته می‌شه.
نیازمندی: ffmpeg باید روی سرور نصب باشه (apt install ffmpeg).
"""

import io
import os
import logging
import subprocess
import tempfile
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from telegram import Update
from telegram.ext import ContextTypes

import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
TGJU_URL = "https://call4.tgju.org/ajax.json"

USER_AGENT = "Mozilla/5.0 (compatible; TelegramBot/1.0; +https://core.telegram.org/bots)"

# دلار و طلا رمزارز نیستن، برای همین از یه منبع عمومی دیگه (tgju) میان
FIAT_GOLD_MAP = {
    "دلار": ("price_dollar_rl", "💵", "dollar"),
    "طلا": ("geram18", "🥇", "gold"),
}

# اسم فارسی -> (نماد کوتاه, ایموجی) — فقط تتر
SYMBOL_MAP = {
    "تتر": ("usdt", "💵"),
}

# نماد کوتاه -> آیدیِ همون کوین تو CoinGecko
COINGECKO_IDS = {
    "usdt": "tether",
}

# ترجمه اسم هر مورد به زبان‌های دیگه (برای نمایش داخل عکس)
NAME_TRANSLATIONS = {
    "usdt": {"fa": "تتر", "en": "Tether", "ar": "تيثر"},
    "dollar": {"fa": "دلار", "en": "US Dollar", "ar": "الدولار الأمريكي"},
    "gold": {"fa": "طلا (۱۸ عیار)", "en": "Gold (18k)", "ar": "الذهب (18 قيراط)"},
}

UI_STRINGS = {
    "fa": {
        "greeting": "سلام جوان ایرانی", "price_label": "قیمت لحظه‌ای", "currency": "تومان",
        "change_suffix": "تغییر نسبت به دیروز", "updated": "بروزرسانی", "unknown": "نامشخص",
    },
    "en": {
        "greeting": "Hello Iranian Youth", "price_label": "Live Price", "currency": "Toman",
        "change_suffix": "change vs yesterday", "updated": "Updated", "unknown": "N/A",
    },
    "ar": {
        "greeting": "مرحباً أيها الشاب الإيراني", "price_label": "السعر اللحظي", "currency": "تومان",
        "change_suffix": "التغيير مقارنة بالأمس", "updated": "آخر تحديث", "unknown": "غير معروف",
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


# ---------------------------------------------------------------------------
# دریافت داده: CoinGecko برای تتر، tgju برای نرخ دلار/طلا
# ---------------------------------------------------------------------------

def fetch_coingecko_data():
    """قیمت دلاریِ تتر رو از CoinGecko می‌گیره"""
    ids = ",".join(sorted(set(COINGECKO_IDS.values())))
    params = {
        "ids": ids,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_price_toman(cg_data: dict, symbol: str, usd_to_toman):
    """
    قیمت یک رمزارز به تومان + درصد تغییر ۲۴ ساعته رو برمی‌گردونه.
    usd_to_toman: نرخ لحظه‌ایِ هر دلار به تومان (از tgju)
    """
    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id:
        return None, None
    entry = cg_data.get(cg_id)
    if not entry:
        return None, None
    usd_price = entry.get("usd")
    change = entry.get("usd_24h_change")
    if usd_price is None or usd_to_toman is None:
        return None, change
    try:
        price_toman = int(float(usd_price) * float(usd_to_toman))
    except (TypeError, ValueError):
        return None, change
    return price_toman, change


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


def get_usd_to_toman_rate(tgju_data: dict):
    """نرخ لحظه‌ایِ هر دلار به تومان (برای تبدیل قیمت دلاریِ تتر)"""
    rate, _ = get_fiat_gold_price(tgju_data, "price_dollar_rl")
    return rate


def _card_color(day_change):
    try:
        if day_change is not None and float(day_change) < 0:
            return (255, 90, 90)  # قرمز برای منفی
    except (TypeError, ValueError):
        pass
    return (90, 200, 130)  # سبز برای مثبت یا نامشخص


COIN_COLORS = {
    "usdt": (38, 161, 123),
    "dollar": (90, 160, 230),
    "gold": (222, 180, 90),
}


def _coin_color(symbol):
    return COIN_COLORS.get(symbol, (147, 51, 234))


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


BG_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "price_card_bg.jpg")
BG_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "assets", "price_card_bg.mp4")


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


def _glass_panel(img, x0, y0, x1, y1, radius=32, blur=14, white_mix=0.06):
    """
    افکت شیشه‌ی مات واقعی (مثل پنل‌های iOS): همون قسمت از پس‌زمینه رو
    بلور می‌کنه، یه‌کم سفید باهاش قاطی می‌کنه (حس شیشه‌ی مه‌گرفته)،
    و با یه ماسک گردشده جاش می‌ذاره. بدون خط دور، بدون کادر اضافه.
    """
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    region = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur))
    white_layer = Image.new("RGB", region.size, (255, 255, 255))
    region = Image.blend(region, white_layer, white_mix)

    mask = Image.new("L", region.size, 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, region.size[0] - 1, region.size[1] - 1], radius=radius, fill=255)

    img = img.copy()
    img.paste(region, (x0, y0), mask)
    return img


def render_single_card(symbol: str, price, change, lang: str = "fa", extra_info=None) -> Image.Image:
    width, height = 1200, 675  # نسبت دقیق 16:9
    gold = (235, 180, 90)  # طلایی/کهربایی هماهنگ با پس‌زمینه
    name = _tr_name(symbol, lang)

    img = _load_background(width, height)

    # پنل شیشه‌ای مات (بدون خط دور، بدون گوشه‌های تزئینی)
    panel_margin = 70
    img = _glass_panel(img, panel_margin, panel_margin, width - panel_margin, height - panel_margin)
    draw = ImageDraw.Draw(img)

    greeting_font = _get_font(24)
    name_font = _get_font(54)
    price_label_font = _get_font(24)
    price_font = _get_font(72)
    change_font = _get_font(30)
    footer_font = _get_font(20)
    detail_font = _get_font(22)

    greeting_text = _fa(_ui(lang, "greeting"))
    gw = draw.textlength(greeting_text, font=greeting_font)
    draw.text(((width - gw) / 2, 118), greeting_text, font=greeting_font, fill=(235, 225, 210))

    name_text = _fa(name)
    nw = draw.textlength(name_text, font=name_font)
    draw.text(((width - nw) / 2, 168), name_text, font=name_font, fill=(255, 255, 255))

    price_label = _fa(_ui(lang, "price_label"))
    plw = draw.textlength(price_label, font=price_label_font)
    draw.text(((width - plw) / 2, 272), price_label, font=price_label_font, fill=(225, 210, 190))

    currency = _ui(lang, "currency")
    price_text = _fa(f"{price:,} {currency}") if price is not None else _fa(_ui(lang, "unknown"))
    pw = draw.textlength(price_text, font=price_font)
    draw.text(((width - pw) / 2, 306), price_text, font=price_font, fill=gold)

    y_cursor = 400
    color = _card_color(change)
    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            change_text = _fa(f"{sign}{change_val:.2f}٪ {_ui(lang, 'change_suffix')}")
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
    footer_text = _fa(f"{_ui(lang, 'updated')}: {format_persian_datetime()}")
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) / 2, height - panel_margin - 44), footer_text, font=footer_font, fill=(220, 205, 180))

    return img


def render_video_price_overlay(symbol: str, price, change, lang: str = "fa",
                                width: int = 1200, height: int = 675) -> Image.Image:
    """
    مثل render_single_card ولی بدون پس‌زمینه (کاملاً شفاف/RGBA)، فقط پنل+متن.
    این تصویر بعداً با ffmpeg روی فریم‌های ویدیو overlay می‌شه.

    width/height: ابعاد دقیق ویدیویی که overlay قراره روش گذاشته بشه (هر
    عرض/ارتفاعی که کاربر آپلود کنه). همه‌ی فونت‌ها و فاصله‌ها نسبت به یه
    طرح پایه‌ی 1200x675 مقیاس داده می‌شن، تا روی هر نسبت تصویری (افقی،
    عمودی، مربعی و...) درست و بدون کشیدگی/برش نمایش داده بشه.
    """
    base_w, base_h = 1200, 675
    scale = min(width / base_w, height / base_h)

    def sc(v):
        return max(1, int(round(v * scale)))

    gold = (235, 180, 90)
    name = _tr_name(symbol, lang)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # پنل نیمه‌شفاف تیره، وسط‌چین شده، با نسبت طرح پایه (بدون کشیدگی)
    panel_margin_x = max(0, (width - sc(base_w - 2 * 70)) // 2)
    panel_margin_y = max(0, (height - sc(base_h - 2 * 70)) // 2)
    panel_w = width - 2 * panel_margin_x
    panel_h = height - 2 * panel_margin_y
    panel = Image.new("RGBA", (panel_w, panel_h), (10, 6, 20, 150))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, panel.size[0] - 1, panel.size[1] - 1], radius=sc(32), fill=255
    )
    img.paste(panel, (panel_margin_x, panel_margin_y), mask)

    greeting_font = _get_font(sc(24))
    name_font = _get_font(sc(54))
    price_label_font = _get_font(sc(24))
    price_font = _get_font(sc(72))
    change_font = _get_font(sc(30))
    footer_font = _get_font(sc(20))

    cx = width / 2

    greeting_text = _fa(_ui(lang, "greeting"))
    gw = draw.textlength(greeting_text, font=greeting_font)
    draw.text((cx - gw / 2, panel_margin_y + sc(48)), greeting_text, font=greeting_font, fill=(235, 225, 210, 255))

    name_text = _fa(name)
    nw = draw.textlength(name_text, font=name_font)
    draw.text((cx - nw / 2, panel_margin_y + sc(98)), name_text, font=name_font, fill=(255, 255, 255, 255))

    price_label = _fa(_ui(lang, "price_label"))
    plw = draw.textlength(price_label, font=price_label_font)
    draw.text((cx - plw / 2, panel_margin_y + sc(202)), price_label, font=price_label_font, fill=(225, 210, 190, 255))

    currency = _ui(lang, "currency")
    price_text = _fa(f"{price:,} {currency}") if price is not None else _fa(_ui(lang, "unknown"))
    pw = draw.textlength(price_text, font=price_font)
    draw.text((cx - pw / 2, panel_margin_y + sc(236)), price_text, font=price_font, fill=gold + (255,))

    y_cursor = panel_margin_y + sc(330)
    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            change_text = _fa(f"{sign}{change_val:.2f}٪ {_ui(lang, 'change_suffix')}")
            cw = draw.textlength(change_text, font=change_font)
            draw.text(
                (cx - cw / 2, y_cursor),
                change_text,
                font=change_font,
                fill=_card_color(change) + (255,),
            )
        except (TypeError, ValueError):
            pass

    from persian_date import format_persian_datetime
    footer_text = _fa(f"{_ui(lang, 'updated')}: {format_persian_datetime()}")
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(
        (cx - fw / 2, panel_margin_y + panel_h - sc(44)),
        footer_text,
        font=footer_font,
        fill=(220, 205, 180, 255),
    )

    return img


def _get_video_dimensions(path):
    """عرض و ارتفاع واقعی فایل ویدیو رو با ffprobe برمی‌گردونه (هر ابعادی که باشه)"""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        path,
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    w_str, h_str = result.stdout.strip().split("x")
    return int(w_str), int(h_str)


def _burn_overlay_on_video(overlay_img: Image.Image) -> str:
    """
    overlay_img (PNG شفاف) رو با ffmpeg روی فریم‌های BG_VIDEO_PATH می‌کشه
    و مسیر فایل ویدیوی نهایی (mp4) رو برمی‌گردونه. صدای اصلی ویدیو
    (اگه داشته باشه) دست‌نخورده کپی می‌شه.
    فراخوان مسئول پاک کردن فایل خروجی بعد از استفاده‌ست.
    """
    overlay_path = tempfile.mktemp(suffix=".png")
    overlay_img.save(overlay_path)
    out_path = tempfile.mktemp(suffix=".mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", BG_VIDEO_PATH,
        "-i", overlay_path,
        "-filter_complex",
        "[0:v][1:v]overlay=0:0:shortest=1",
        "-c:a", "copy",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        raise RuntimeError(f"ffmpeg overlay failed: {stderr[-800:]}") from e
    finally:
        if os.path.exists(overlay_path):
            os.remove(overlay_path)

    return out_path


def _image_to_bytes(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "price.png"
    return buf



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


async def _auto_delete_price_message(context: ContextTypes.DEFAULT_TYPE):
    """چند ثانیه بعد از ارسال، پیام(های) قیمت رو (فقط تو پی‌وی) پاک می‌کنه"""
    job = context.job
    message_ids = job.data
    if isinstance(message_ids, int):
        message_ids = [message_ids]
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=job.chat_id, message_id=msg_id)
        except Exception:
            pass


def _schedule_auto_delete(context: ContextTypes.DEFAULT_TYPE, chat, message_ids, delay: int = 60):
    """
    اگه چت از نوع پی‌وی بود و job_queue در دسترس بود، حذف خودکار رو زمان‌بندی می‌کنه.
    message_ids می‌تونه یک عدد باشه یا یک لیست از چند آیدیِ پیام (مثلاً هم پیام
    خودِ کاربر هم پیام قیمتی که ربات فرستاده) که همه با هم بعد از delay ثانیه پاک می‌شن.
    """
    if not chat or chat.type != "private":
        return
    if not context.job_queue:
        return
    context.job_queue.run_once(
        _auto_delete_price_message, delay, chat_id=chat.id, data=message_ids
    )


DEBUG_VIDEO_ERRORS = True  # وقتی کار درست شد، این رو False کن تا خطاها فقط تو لاگ بمونن


async def _send_price_result(update: Update, context: ContextTypes.DEFAULT_TYPE, chat, symbol, price, change, lang, caption):
    """
    اگه ویدیوی پس‌زمینه (assets/price_card_bg.mp4) وجود داشت، یک PNG شفاف
    شامل قیمت لحظه‌ای می‌سازه، با ffmpeg روی فریم‌های ویدیو overlay
    (burn-in) می‌کنه و همون رو با کپشن می‌فرسته. چون قیمت هر بار فرق
    می‌کنه، ویدیوی نهایی کش نمی‌شه - هر بار از نو ساخته می‌شه.
    اگه ساخت ویدیو به هر دلیلی شکست بخوره (مثلاً ffmpeg نصب نباشه)،
    به همون روش قبلی (عکس با متن قیمت) برمی‌گرده.
    وقتی DEBUG_VIDEO_ERRORS روشنه، متن دقیق خطا رو هم به‌عنوان یه پیام
    جدا تو همون چت می‌فرسته تا بدون رفتن سراغ لاگ سرور، خود کاربر ببینتش.
    """
    message = update.effective_message
    sent = None

    if os.path.exists(BG_VIDEO_PATH):
        out_path = None
        try:
            try:
                vid_w, vid_h = _get_video_dimensions(BG_VIDEO_PATH)
            except Exception:
                vid_w, vid_h = 1200, 675  # اگه ffprobe شکست خورد، فرض پیش‌فرض
            overlay_img = render_video_price_overlay(symbol, price, change, lang=lang, width=vid_w, height=vid_h)
            out_path = _burn_overlay_on_video(overlay_img)
            with open(out_path, "rb") as f:
                sent = await message.reply_video(video=f, caption=caption)
        except Exception as e:
            logger.warning(f"ساخت ویدیوی قیمت‌دار ناموفق بود، برگشت به عکس: {e}")
            if DEBUG_VIDEO_ERRORS:
                try:
                    err_text = str(e)[:1500]
                    await message.reply_text(f"⚠️ خطای ساخت ویدیو (دیباگ):\n{err_text}")
                except Exception:
                    pass
            sent = None
        finally:
            if out_path and os.path.exists(out_path):
                os.remove(out_path)

    if sent is None:
        img = render_single_card(symbol, price, change, lang=lang)
        sent = await message.reply_photo(photo=_image_to_bytes(img), caption=caption)

    _schedule_auto_delete(context, chat, [message.message_id, sent.message_id])


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
        caption = _build_caption(trans_key, price, change, lang=lang)
        await _send_price_result(update, context, chat, trans_key, price, change, lang, caption)
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
            cg_data = fetch_coingecko_data()
        except Exception as e:
            await update.effective_message.reply_text(f"❌ نتونستم به CoinGecko وصل بشم.\n{e}")
            return

        price, change = get_price_toman(cg_data, symbol, usd_toman)
        caption = _build_caption(symbol, price, change, lang=lang)
        await _send_price_result(update, context, chat, symbol, price, change, lang, caption)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ خطای غیرمنتظره تو ساختن قیمت {text}.\n{e}")
