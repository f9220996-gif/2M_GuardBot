# -*- coding: utf-8 -*-
"""
تولید متن تاریخ/ساعت به فرمت فارسی، دقیقا مثل پیام رسمی محدودیت تلگرام:
مثال: "03 اوت، 2:34 ب.ظ"
"""

from datetime import datetime

PERSIAN_MONTHS = {
    1: "ژانویه", 2: "فوریه", 3: "مارس", 4: "آوریل",
    5: "می", 6: "ژوئن", 7: "ژوئیه", 8: "اوت",
    9: "سپتامبر", 10: "اکتبر", 11: "نوامبر", 12: "دسامبر",
}


def format_persian_datetime(dt: datetime) -> str:
    day = dt.strftime("%d")
    month = PERSIAN_MONTHS[dt.month]
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    minute = dt.strftime("%M")
    period = "ب.ظ" if dt.hour >= 12 else "ق.ظ"
    return f"{day} {month}، {hour12}:{minute} {period}"


def build_restriction_message(until_dt: datetime, group_title: str | None = None) -> str:
    """متن رسمی سبک تلگرام برای اطلاع‌رسانی سکوت کاربر"""
    when = format_persian_datetime(until_dt)
    if group_title:
        return f"مدیران گروه «{group_title}»، امکان ارسال پیام را برای شما تا {when} محدود کرده‌اند."
    return f"مدیران این گروه، امکان ارسال پیام را برای شما تا {when} محدود کرده‌اند."


def build_duration_text(seconds: int) -> str:
    """تبدیل ثانیه به متن خوانا مثل «۵ ساعت و ۳۰ دقیقه»"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h} ساعت")
    if m:
        parts.append(f"{m} دقیقه")
    if s:
        parts.append(f"{s} ثانیه")
    return " و ".join(parts) if parts else "چند لحظه"
