# -*- coding: utf-8 -*-
"""
بررسی وبهوک: اگه قبلا وبهوکی روی این ربات ست شده باشه،
با polling تداخل پیدا می‌کنه و ربات هیچ‌وقت آپدیت نمی‌گیره.
اجرا: python check_webhook.py
"""

import asyncio
from telegram import Bot
from config import BOT_TOKEN


async def main():
    bot = Bot(BOT_TOKEN)
    info = await bot.get_webhook_info()
    print("آدرس وبهوک فعلی:", info.url or "(هیچی — یعنی مشکلی از این بابت نیست)")
    print("تعداد آپدیت‌های در انتظار:", info.pending_update_count)
    if info.last_error_message:
        print("آخرین خطای وبهوک:", info.last_error_message)

    if info.url:
        print("\n⚠️ وبهوک فعاله و باید حذفش کنیم تا polling کار کنه...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ وبهوک حذف شد. حالا دوباره python main.py رو اجرا کن.")
    else:
        print("\n✅ وبهوکی وجود نداره، مشکل چیز دیگه‌ایه.")


if __name__ == "__main__":
    asyncio.run(main())
