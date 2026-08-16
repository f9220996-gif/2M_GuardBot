# -*- coding: utf-8 -*-
"""
ماژول ساخت کارت قیمت با افکت شیشه‌ای (Glassmorphism)
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import arabic_reshaper
from bidi.algorithm import get_display

# ========== تنظیمات فونت ==========
FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "Vazirmatn-Bold.ttf")
FALLBACK_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "DejaVuSans-Bold.ttf")
BG_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "price_card_bg.jpg")

def _get_font(size):
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    if os.path.exists(FALLBACK_FONT_PATH):
        return ImageFont.truetype(FALLBACK_FONT_PATH, size)
    return ImageFont.load_default()

def _fa(text: str) -> str:
    """متن فارسی رو برای نمایش درست آماده می‌کنه"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def _load_background(width, height):
    """بارگذاری تصویر پس‌زمینه"""
    if not os.path.exists(BG_IMAGE_PATH):
        # اگر تصویر نبود، گرادیان تیره بساز
        img = Image.new("RGB", (width, height), (18, 10, 34))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / height
            r = int(18 + (10 - 18) * t)
            g = int(10 + (6 - 10) * t)
            b = int(34 + (18 - 34) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        return img
    
    bg = Image.open(BG_IMAGE_PATH).convert("RGB")
    bg = bg.resize((width, height), Image.LANCZOS)
    return bg

def render_single_card(name: str, emoji: str, price, change, extra_info=None) -> Image.Image:
    """
    ساخت کارت قیمت با افکت شیشه‌ای
    
    Args:
        name: نام رمزارز (مثلاً "بیت‌کوین")
        emoji: ایموجی مربوطه (مثلاً "🟠")
        price: قیمت به تومان
        change: درصد تغییر
        extra_info: لیست اطلاعات اضافی
    """
    width, height = 1000, 620
    
    # ===== پس‌زمینه =====
    bg = _load_background(width, height)
    # تاری خفیف برای بهتر دیدن متن
    bg_blurred = bg.filter(ImageFilter.GaussianBlur(radius=1.5))
    img = bg_blurred.copy()
    
    # ===== پنل شیشه‌ای =====
    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel)
    
    panel_margin = 50
    panel_radius = 35
    
    # بدنه شیشه‌ای
    panel_draw.rounded_rectangle(
        [panel_margin, panel_margin, width - panel_margin, height - panel_margin],
        radius=panel_radius,
        fill=(255, 255, 255, 20),  # شفافیت بالا
        outline=(255, 255, 255, 50),  # حاشیه سفید نیمه‌شفاف
        width=2
    )
    
    # هایلایت شیشه (درخشش)
    shine = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)
    
    # هایلایت بالا سمت چپ
    shine_draw.ellipse(
        [panel_margin + 40, panel_margin + 20, panel_margin + 250, panel_margin + 80],
        fill=(255, 255, 255, 25)
    )
    
    # هایلایت پایین سمت راست (کم‌رنگ‌تر)
    shine_draw.ellipse(
        [width - panel_margin - 280, height - panel_margin - 70, 
         width - panel_margin - 60, height - panel_margin - 20],
        fill=(255, 255, 255, 10)
    )
    
    # ترکیب لایه‌ها
    img = Image.alpha_composite(img.convert("RGBA"), panel)
    img = Image.alpha_composite(img, shine)
    
    draw = ImageDraw.Draw(img)
    
    # ===== رنگ‌ها =====
    gold = (255, 200, 70)
    white = (255, 255, 255)
    soft_white = (230, 225, 240)
    
    # ===== فونت‌ها =====
    greeting_font = _get_font(22)
    name_font = _get_font(50)
    emoji_font = _get_font(42)
    price_label_font = _get_font(22)
    price_font = _get_font(65)
    change_font = _get_font(28)
    footer_font = _get_font(18)
    extra_font = _get_font(20)
    
    # ===== متن خوش‌آمدگویی =====
    greeting = _fa("سلام جوان ایرانی")
    gw = draw.textlength(greeting, font=greeting_font)
    draw.text(((width - gw) / 2, 115), greeting, font=greeting_font, fill=soft_white)
    
    # ===== اسم + ایموجی =====
    name_text = _fa(name)
    nw = draw.textlength(name_text, font=name_font)
    ew = draw.textlength(emoji, font=emoji_font)
    total_width = nw + ew + 15
    start_x = (width - total_width) / 2
    
    draw.text((start_x, 155), emoji, font=emoji_font, fill=white)
    draw.text((start_x + ew + 15, 160), name_text, font=name_font, fill=white)
    
    # ===== قیمت =====
    price_label = _fa("قیمت لحظه‌ای")
    plw = draw.textlength(price_label, font=price_label_font)
    draw.text(((width - plw) / 2, 235), price_label, font=price_label_font, fill=soft_white)
    
    if price is not None:
        price_text = _fa(f"{price:,} تومان")
    else:
        price_text = _fa("نامشخص")
    pw = draw.textlength(price_text, font=price_font)
    draw.text(((width - pw) / 2, 270), price_text, font=price_font, fill=gold)
    
    # ===== تغییرات =====
    y_cursor = 370
    if change is not None:
        try:
            change_val = float(change)
            sign = "+" if change_val >= 0 else ""
            change_color = (90, 200, 130) if change_val >= 0 else (255, 90, 90)
            change_text = _fa(f"{sign}{change_val:.2f}٪ تغییر نسبت به دیروز")
            cw = draw.textlength(change_text, font=change_font)
            draw.text(((width - cw) / 2, y_cursor), change_text, font=change_font, fill=change_color)
            y_cursor += 45
        except (TypeError, ValueError):
            pass
    
    # ===== اطلاعات اضافی =====
    if extra_info:
        for line in extra_info:
            line_text = _fa(line)
            lw = draw.textlength(line_text, font=extra_font)
            draw.text(((width - lw) / 2, y_cursor), line_text, font=extra_font, fill=soft_white)
            y_cursor += 32
    
    # ===== فوتر =====
    try:
        from persian_date import format_persian_datetime
        footer_text = _fa(f"بروزرسانی: {format_persian_datetime()}")
    except:
        footer_text = _fa("بروزرسانی: لحظه‌ای")
    
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) / 2, height - 45), footer_text, font=footer_font, fill=(200, 195, 210))
    
    return img

def image_to_bytes(img: Image.Image) -> io.BytesIO:
    """تبدیل تصویر به بایت برای ارسال در تلگرام"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "price.png"
    return buf
