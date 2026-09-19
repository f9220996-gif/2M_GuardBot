# -*- coding: utf-8 -*-
"""
ماژول قیمت ارزهای دیجیتال، دلار و طلا.

- قیمت ارزهای دیجیتال از API عمومی CoinGecko گرفته می‌شه (بر حسب دلار آمریکا).
- قیمت دلار/یورو از API عمومی exchangerate.host گرفته می‌شه.
- قیمت طلا (اونس جهانی) از یک API عمومی گرفته می‌شه.

نکته‌ی مهم: این قیمت‌ها نرخ‌های جهانی/بین‌المللی هستن، نه نرخ بازار آزاد ایران
(صرافی/طلافروشی). اگه به نرخ بازار آزاد ایران نیاز داری، باید تابع
_fetch_fiat_rate رو با یک API داخلی مناسب (مثل نوسان، بن‌بست و مشابه) جایگزین کنی.

وابستگی: این فایل از aiohttp استفاده می‌کنه. مطمئن شو در requirements.txt
پروژه‌ات خط زیر وجود داره:
    aiohttp
"""

import logging
from typing import Optional

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ===== نگاشت نام فارسی ارز دیجیتال -> شناسه‌ی CoinGecko =====
SYMBOL_MAP = {
    "بیت کوین": "bitcoin",
    "بیتکوین": "bitcoin",
    "اتریوم": "ethereum",
    "تتر": "tether",
    "بایننس کوین": "binancecoin",
    "ریپل": "ripple",
    "ریپل کوین": "ripple",
    "دوج کوین": "dogecoin",
    "کاردانو": "cardano",
    "سولانا": "solana",
    "لایت کوین": "litecoin",
    "ترون": "tron",
    "پولکادات": "polkadot",
    "شیبا": "shiba-inu",
    "شیبا اینو": "shiba-inu",
}

# ===== نگاشت نام فارسی ارز فیات/طلا -> کد =====
FIAT_GOLD_MAP = {
    "دلار": "USD",
    "یورو": "EUR",
    "طلا": "XAU",
}

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
FOREX_URL = "https://api.exchangerate.host/latest"
GOLD_URL = "https://api.gold-api.com/price/XAU"

_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def _fetch_crypto_price(coin_id: str, vs_currency: str = "usd") -> Optional[float]:
    """قیمت یک ارز دیجیتال رو بر حسب دلار از CoinGecko می‌گیره."""
    params = {"ids": coin_id, "vs_currencies": vs_currency}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(COINGECKO_URL, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"CoinGecko status {resp.status} for {coin_id}")
                    return None
                data = await resp.json()
                return data.get(coin_id, {}).get(vs_currency)
    except Exception as e:
        logger.warning(f"crypto price fetch failed for {coin_id}: {e}")
        return None


async def _fetch_gold_price() -> Optional[float]:
    """قیمت جهانی هر اونس طلا بر حسب دلار."""
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(GOLD_URL) as resp:
                if resp.status != 200:
                    logger.warning(f"gold API status {resp.status}")
                    return None
                data = await resp.json()
                price = data.get("price")
                return float(price) if price is not None else None
    except Exception as e:
        logger.warning(f"gold price fetch failed: {e}")
        return None


async def _fetch_forex_rate(code: str) -> Optional[float]:
    """نرخ برابری یک ارز فیات (مثل دلار یا یورو) بر حسب دلار آمریکا."""
    if code == "USD":
        return 1.0
    try:
        params = {"base": code, "symbols": "USD"}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(FOREX_URL, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"forex API status {resp.status} for {code}")
                    return None
                data = await resp.json()
                return data.get("rates", {}).get("USD")
    except Exception as e:
        logger.warning(f"forex rate fetch failed for {code}: {e}")
        return None


async def _fetch_fiat_rate(code: str) -> Optional[float]:
    """مسیریابی بین طلا و بقیه‌ی ارزهای فیات."""
    if code == "XAU":
        return await _fetch_gold_price()
    return await _fetch_forex_rate(code)


async def cmd_crypto_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    وقتی کاربر اسم یه ارز دیجیتال یا دلار/طلا رو مستقیم توی گروه یا پی‌وی
    تایپ می‌کنه (مثلاً «بیت کوین» یا «دلار»)، این تابع قیمتش رو جواب می‌ده.
    """
    message = update.effective_message
    if not message:
        return

    text = (message.text or "").strip()

    if text in SYMBOL_MAP:
        coin_id = SYMBOL_MAP[text]
        price = await _fetch_crypto_price(coin_id)
        if price is None:
            await message.reply_text(
                "⚠️ در حال حاضر امکان دریافت قیمت وجود نداره. لطفاً چند لحظه دیگه دوباره امتحان کن."
            )
            return
        await message.reply_text(f"💰 قیمت {text}: {price:,.2f} دلار")
        return

    if text in FIAT_GOLD_MAP:
        code = FIAT_GOLD_MAP[text]
        rate = await _fetch_fiat_rate(code)
        if rate is None:
            await message.reply_text(
                "⚠️ در حال حاضر امکان دریافت قیمت وجود نداره. لطفاً چند لحظه دیگه دوباره امتحان کن."
            )
            return
        unit = "دلار" if code == "XAU" else "دلار آمریکا"
        await message.reply_text(f"💵 قیمت {text}: {rate:,.2f} {unit}")
        return

    # اگه به هر دلیلی متن پیام تو هیچ‌کدوم از نقشه‌ها نبود، کاری نکن
    return
