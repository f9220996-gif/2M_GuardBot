# -*- coding: utf-8 -*-
"""
توابع کمکی برای:
 - تشخیص سطح دسترسی (سازنده ربات / مالک گروه / مدیر / کاربر عادی)
 - پارس کردن رشته‌های زمانی مثل "5h" "10m30s" "1h20m"
"""

import re
from telegram import Chat, ChatMember

import database as db
from config import CREATOR_ID

TIME_PATTERN = re.compile(r"(\d+)\s*(h|m|s|ساعت|دقیقه|ثانیه)", re.IGNORECASE)


def parse_duration_seconds(text: str):
    """
    ورودی مثل '5h' یا '10m' یا '1h30m' یا '45s' را به ثانیه تبدیل می‌کند.
    اگر چیزی پیدا نشود None برمی‌گرداند.
    """
    if not text:
        return None
    total = 0
    found = False
    for amount, unit in TIME_PATTERN.findall(text):
        found = True
        amount = int(amount)
        unit = unit.lower()
        if unit in ("h", "ساعت"):
            total += amount * 3600
        elif unit in ("m", "دقیقه"):
            total += amount * 60
        elif unit in ("s", "ثانیه"):
            total += amount
    return total if found else None


async def is_creator(user_id: int) -> bool:
    return CREATOR_ID != 0 and user_id == CREATOR_ID


async def is_group_owner(chat_id: int, user_id: int) -> bool:
    """کسی که ربات را داخل گروه اضافه کرده، به عنوان 'مالک' از دید ربات شناخته می‌شود"""
    group = db.get_group(chat_id)
    return bool(group and group["added_by_user_id"] == user_id)


async def is_telegram_group_creator(bot, chat_id: int, user_id: int) -> bool:
    """چک کردن نقش واقعی 'creator' گروه از API تلگرام"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status == ChatMember.OWNER
    except Exception:
        return False


async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False


async def get_permission_level(bot, chat_id: int, user_id: int) -> str:
    """
    برمی‌گرداند یکی از:
    'creator'      -> سازنده ربات (دسترسی کامل روی همه گروه‌ها)
    'group_owner'  -> مالک/سازنده همان گروه (دسترسی کامل روی گروه خودش)
    'admin'        -> مدیر عادی گروه
    'member'       -> کاربر عادی
    """
    if await is_creator(user_id):
        return "creator"
    if await is_group_owner(chat_id, user_id) or await is_telegram_group_creator(bot, chat_id, user_id):
        return "group_owner"
    if await is_admin(bot, chat_id, user_id):
        return "admin"
    return "member"


async def can_use_moderation_commands(bot, chat_id: int, user_id: int) -> bool:
    """آیا این کاربر اجازه دارد دستورات مدیریتی (بن/سکوت/قفل و ...) را اجرا کند"""
    level = await get_permission_level(bot, chat_id, user_id)
    return level in ("creator", "group_owner", "admin")


async def can_target_user(bot, chat_id: int, actor_id: int, target_id: int) -> bool:
    """
    آیا actor اجازه دارد روی target عملیات مدیریتی (بن/سکوت) انجام دهد؟
    قانون: مدیران عادی نمی‌توانند روی همدیگر یا روی مالک گروه عملیات انجام دهند،
    مگر اینکه مالک گروه از پنل اجازه ویژه داده باشد.
    سازنده ربات و مالک گروه محدودیتی ندارند.
    """
    actor_level = await get_permission_level(bot, chat_id, actor_id)
    target_level = await get_permission_level(bot, chat_id, target_id)

    if actor_level == "creator":
        return True
    if actor_level == "group_owner":
        return True
    if actor_level == "admin":
        if target_level in ("creator", "group_owner"):
            return False
        if target_level == "admin":
            # فقط اگر مالک گروه صراحتا اجازه داده باشد
            return db.has_admin_extra_permission(chat_id, actor_id)
        return True  # روی کاربر عادی مشکلی نیست
    return False
