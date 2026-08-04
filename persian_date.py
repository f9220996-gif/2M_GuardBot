# -*- coding: utf-8 -*-
"""
تولید متن تاریخ/ساعت شمسی (جلالی) واقعی با استفاده از کتابخانه jdatetime.
"""

from datetime import datetime
import jdatetime


def format_persian_date_only(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405"""
    if dt is None:
        dt = datetime.now()
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    return jd.strftime("%d %B %Y")


def format_persian_time_only(dt: datetime = None) -> str:
    """مثال خروجی: 2:34 ب.ظ"""
    if dt is None:
        dt = datetime.now()
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    minute = dt.strftime("%M")
    period = "ب.ظ" if dt.hour >= 12 else "ق.ظ"
    return f"{hour12}:{minute} {period}"


def format_persian_datetime(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405، 2:34 ب.ظ"""
    if dt is None:
        dt = datetime.now()
    return f"{format_persian_date_only(dt)}، {format_persian_time_only(dt)}"


def build_restriction_message(until_dt: datetime, group_title: str = None) -> str:
    """متن رسمی سبک تلگرام برای اطلاع‌رسانی سکوت کاربر، با تاریخ شمسی"""
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


async def cmd_tarikh(update, context):
    """دستور «تاریخ»: هرکسی تو گروه بنویسه، تاریخ و ساعت شمسی الان رو نشون می‌ده"""
    now = datetime.now()
    weekday_names = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    jd = jdatetime.datetime.fromgregorian(datetime=now)
    weekday = weekday_names[jd.weekday()]
    text = (
        f"📅 {weekday}، {format_persian_date_only(now)}\n"
        f"🕒 {format_persian_time_only(now)}"
    )
    await update.effective_message.reply_text(text)
