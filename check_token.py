# -*- coding: utf-8 -*-
"""
اسکریپت تست سریع: فقط چک می‌کنه توکن شما متعلق به کدوم ربات هست.
اجرا: python check_token.py
"""

import asyncio
from telegram import Bot
from config import BOT_TOKEN


async def main():
    print("توکن استفاده‌شده:", BOT_TOKEN[:15] + "..." if len(BOT_TOKEN) > 15 else BOT_TOKEN)
    try:
        bot = Bot(BOT_TOKEN)
        me = await bot.get_me()
        print("✔ اتصال موفق بود!")
        print("نام ربات:", me.full_name)
        print("یوزرنیم ربات:", "@" + me.username)
        print("آیدی عددی ربات:", me.id)
    except Exception as e:
        print("✔ اتصال ناموفق بود. خطا:")
        print(e)


if __name__ == "__main__":
    asyncio.run(main())
