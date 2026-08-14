# -*- coding: utf-8 -*-
"""
تولید متن تاریخ/ساعت شمسی (جلالی) واقعی با استفاده از کتابخانه jdatetime.
سرور (Railway) به‌وقت UTC کار می‌کنه، برای همین همه‌جا صریحاً به وقت تهران تبدیل می‌کنیم.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import jdatetime

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def now_tehran() -> datetime:
    """زمان فعلی به‌وقت تهران (صرف‌نظر از تایم‌زون سرور)"""
    return datetime.now(TEHRAN_TZ)


def utc_from_ts(ts: float) -> datetime:
    """برای پاس دادن به API تلگرام (که با UTC کار می‌کنه)"""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def tehran_from_ts(ts: float) -> datetime:
    """برای نمایش به کاربر، به‌وقت تهران"""
    return datetime.fromtimestamp(ts, tz=TEHRAN_TZ)


def format_persian_date_only(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405"""
    if dt is None:
        dt = now_tehran()
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    month_name = jd.j_months_fa[jd.month - 1]
    return f"{jd.day} {month_name} {jd.year}"


def format_persian_time_only(dt: datetime = None) -> str:
    """مثال خروجی: 2:34 ب.ظ"""
    if dt is None:
        dt = now_tehran()
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    minute = dt.strftime("%M")
    period = "ب.ظ" if dt.hour >= 12 else "ق.ظ"
    return f"{hour12}:{minute} {period}"


def format_persian_datetime(dt: datetime = None) -> str:
    """مثال خروجی: 14 مرداد 1405، 2:34 ب.ظ"""
    if dt is None:
        dt = now_tehran()
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
    import database as db
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup") and not db.is_feature_enabled(chat.id, "date"):
        return

    now = now_tehran()
    # هفته ایرانی از شنبه شروع می‌شه؛ jdatetime.weekday() هم شنبه=0 تا جمعه=6 برمی‌گردونه
    weekday_names = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    jd = jdatetime.datetime.fromgregorian(datetime=now)
    weekday = weekday_names[jd.weekday()]
    text = (
        f"🗓 تاریخ: {weekday}، {format_persian_date_only(now)}\n"
        f"⏰ ساعت: {now.strftime('%H:%M')}"
    )
    await update.effective_message.reply_text(text)
