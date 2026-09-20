# -*- coding: utf-8 -*-
"""
قابلیت‌های جدید ربات (فایل جدا، بدون دست‌زدن به بقیه‌ی کدها):

  ۱) آمار گروه
       «آمار»        ← آمار امروزِ هر نفر (پیام، عکس، فیلم، گیف، استیکر، لینک)
       «آمار کل»     ← آمار کل گروه از اولین روزی که ربات شروع به شمارش کرده
       ریپلای روی یه نفر + «آمار» یا «آمار کل» ← فقط آمار همون نفر

  ۲) تبدیل ارز
       «۱۰۰ دلار»  /  «۵۰ تتر»  /  «۱۰۰ دلار به تومان»
       «۵ میلیون تومان به دلار»  /  «۲۰۰۰۰۰۰ تومان به تتر»

  ۳) نمودار قیمت
       «نمودار دلار»  /  «نمودار طلا»  /  «نمودار تتر»
       «نمودار دلار هفته»  /  «نمودار دلار ماه»

نصب: تو main.py
       import extras
       extras.register(app)
       و تو guarded_private_text (برای پی‌وی) قبل از چک قیمت‌ها:
       if await extras.handle_text(update, context): return
"""

import asyncio
import html
import io
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from PIL import Image
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

try:
    import crypto as pc          # اسم فایل قیمت‌ها تو پروژه
except ImportError:
    import price_commands as pc   # اگه اسمش این بود

try:
    from matplotlib.figure import Figure
    from matplotlib import font_manager, ticker
    from matplotlib import dates as mdates
    import matplotlib
    HAS_MPL = True
except ImportError:  # نمودار کار نمی‌کنه، ولی بقیه‌ی قابلیت‌ها سالمن
    HAS_MPL = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------

# مسیر دیتابیس. تو Railway حتماً یه Volume وصل کن و مثلاً STATS_DB_PATH=/data/stats.db بذار،
# وگرنه با هر دیپلوی آمار پاک می‌شه.
DB_PATH = os.environ.get("STATS_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.db"))

MAX_PEOPLE = 10                 # حداکثر تعداد نفرات تو لیست آمار گروه
PRICE_SAMPLE_INTERVAL = 600     # هر چند ثانیه یه‌بار قیمت‌ها برای نمودار ذخیره بشن
PRICE_KEEP_DAYS = 35            # قیمت‌های قدیمی‌تر از این پاک می‌شن
AUTO_DELETE_DELAY = 60          # تو پی‌وی، پیام کاربر و جواب ربات بعد از این مدت (ثانیه) پاک می‌شن
RATE_CACHE_SECONDS = 45         # کش نرخ، برای اینکه با هر پیام به tgju/CoinGecko درخواست نره

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = timezone(timedelta(hours=3, minutes=30))

GROUP_TYPES = ("group", "supergroup")

FIELDS = ("messages", "photos", "videos", "gifs", "stickers", "links")
ICONS = {
    "messages": "💬", "photos": "🖼", "videos": "🎬",
    "gifs": "🎞", "stickers": "🎭", "links": "🔗",
}
LABELS = {
    "messages": "پیام", "photos": "عکس", "videos": "فیلم",
    "gifs": "گیف", "stickers": "استیکر", "links": "لینک",
}

async def _auto_delete_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    for message_id in job.data:
        try:
            await context.bot.delete_message(chat_id=job.chat_id, message_id=message_id)
        except Exception:
            pass


def _schedule_delete(context, chat, message_ids, delay: int = AUTO_DELETE_DELAY):
    """فقط تو پی‌وی: پیام‌ها رو بعد از delay ثانیه پاک می‌کنه"""
    if not chat or chat.type != "private" or not context.job_queue:
        return
    context.job_queue.run_once(_auto_delete_job, delay, chat_id=chat.id, data=list(message_ids))


def _feature_ok(chat, key: str) -> bool:
    """اگه قابلیتی (مثل «dollar») تو پنل گروه خاموش شده باشه، اینجا هم کار نمی‌کنه"""
    if not chat or chat.type not in GROUP_TYPES:
        return True
    try:
        import database as db
        return bool(db.is_feature_enabled(chat.id, key))
    except Exception:
        return True


# ---------------------------------------------------------------------------
# ابزارهای متنی: ارقام فارسی، تاریخ شمسی، نرمال‌سازی
# ---------------------------------------------------------------------------

_TO_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def p(x) -> str:
    """هر عدد/متنی رو با ارقام فارسی برمی‌گردونه"""
    return str(x).translate(_TO_FA)


def fmt_int(n) -> str:
    return p(f"{int(round(n)):,}").replace(",", "٬")


def fmt_num(v: float, decimals: int = 2) -> str:
    if float(v).is_integer():
        return fmt_int(v)
    return p(f"{v:,.{decimals}f}").replace(",", "٬").replace(".", "٫")


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_from_iso(iso_day: str) -> str:
    y, m, d = (int(x) for x in iso_day.split("-"))
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    return p(f"{jy}/{jm:02d}/{jd:02d}")


def _norm(text: str) -> str:
    """متن پیام رو برای تطبیق دستورها یکدست می‌کنه (ارقام، ی/ک عربی، نیم‌فاصله، ...)"""
    t = text.translate(_TO_EN)
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = t.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    t = re.sub(r"(?<=\d)[,،٬](?=\d)", "", t)
    t = t.replace("٫", ".")
    t = re.sub(r"[!؟?.]+$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# دیتابیس
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_stats (
    chat_id  INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    day      TEXT    NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0,
    photos   INTEGER NOT NULL DEFAULT 0,
    videos   INTEGER NOT NULL DEFAULT 0,
    gifs     INTEGER NOT NULL DEFAULT 0,
    stickers INTEGER NOT NULL DEFAULT 0,
    links    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, day)
);
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name    TEXT    NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS price_history (
    symbol TEXT    NOT NULL,
    ts     INTEGER NOT NULL,
    price  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_history ON price_history (symbol, ts);
"""

_conn = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def _today_iso() -> str:
    return datetime.now(TEHRAN).strftime("%Y-%m-%d")


def add_counts(chat_id: int, user_id: int, name: str, counts: dict, day: str = None):
    day = day or _today_iso()
    db = _db()
    with db:
        db.execute(
            """INSERT INTO daily_stats (chat_id, user_id, day, messages, photos, videos, gifs, stickers, links)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, user_id, day) DO UPDATE SET
                 messages = messages + excluded.messages,
                 photos   = photos   + excluded.photos,
                 videos   = videos   + excluded.videos,
                 gifs     = gifs     + excluded.gifs,
                 stickers = stickers + excluded.stickers,
                 links    = links    + excluded.links""",
            (chat_id, user_id, day, *[counts[f] for f in FIELDS]),
        )
        db.execute(
            """INSERT INTO users (chat_id, user_id, name) VALUES (?, ?, ?)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET name = excluded.name""",
            (chat_id, user_id, name),
        )


def query_people(chat_id: int, day: str = None):
    """لیست آمار همه‌ی افراد گروه (مرتب‌شده بر اساس تعداد پیام). day=None یعنی کل زمان."""
    sql = """
        SELECT d.user_id, COALESCE(u.name, '؟'),
               SUM(d.messages), SUM(d.photos), SUM(d.videos),
               SUM(d.gifs), SUM(d.stickers), SUM(d.links)
        FROM daily_stats d
        LEFT JOIN users u ON u.chat_id = d.chat_id AND u.user_id = d.user_id
        WHERE d.chat_id = ?"""
    args = [chat_id]
    if day:
        sql += " AND d.day = ?"
        args.append(day)
    sql += " GROUP BY d.user_id ORDER BY SUM(d.messages) DESC, d.user_id"
    rows = []
    for r in _db().execute(sql, args).fetchall():
        item = {"user_id": r[0], "name": r[1]}
        item.update(dict(zip(FIELDS, r[2:])))
        rows.append(item)
    return rows


def query_since(chat_id: int):
    r = _db().execute("SELECT MIN(day) FROM daily_stats WHERE chat_id = ?", (chat_id,)).fetchone()
    return r[0] if r else None


# ---------------------------------------------------------------------------
# شمارش پیام‌ها
# ---------------------------------------------------------------------------

def classify_message(m) -> dict:
    counts = dict.fromkeys(FIELDS, 0)
    counts["messages"] = 1
    if m.sticker:
        counts["stickers"] = 1
    elif m.animation:          # گیف؛ باید قبل از document/video چک بشه
        counts["gifs"] = 1
    elif m.video or m.video_note:
        counts["videos"] = 1
    elif m.photo:
        counts["photos"] = 1
    entities = list(m.entities or []) + list(m.caption_entities or [])
    counts["links"] = sum(1 for e in entities if e.type in ("url", "text_link"))
    return counts


async def count_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not m or not user or not chat or user.is_bot:
        return
    if chat.type not in GROUP_TYPES:
        return
    try:
        name = (user.full_name or user.username or "بدون‌نام").strip()[:30]
        add_counts(chat.id, user.id, name, classify_message(m))
    except Exception as e:
        logger.warning(f"ثبت آمار ناموفق بود: {e}")


# ---------------------------------------------------------------------------
# ساخت متن آمار
# ---------------------------------------------------------------------------

_RANKS = ["🥇", "🥈", "🥉"]
_SEP = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
_LEGEND = "  ·  ".join(f"{ICONS[f]} {LABELS[f]}" for f in FIELDS)


def _compact_line(row: dict) -> str:
    parts = [f"💬 {fmt_int(row['messages'])}"]
    for f in FIELDS[1:]:
        if row[f]:
            parts.append(f"{ICONS[f]} {fmt_int(row[f])}")
    return "  ·  ".join(parts)


def build_group_text(rows, total_mode: bool, since_iso: str = None) -> str:
    if total_mode:
        title = "آمار کل گروه"
        sub = f"🗓 از {jalali_from_iso(since_iso)} تا امروز" if since_iso else ""
        empty = "📭 هنوز آماری ثبت نشده."
    else:
        title = "آمار امروز گروه"
        sub = f"📅 {jalali_from_iso(_today_iso())}"
        empty = "📭 امروز هنوز پیامی ثبت نشده."

    if not rows:
        return f"📊 <b>{title}</b>\n\n{empty}"

    lines = [f"📊 <b>{title}</b>"]
    if sub:
        lines.append(sub)
    lines.append("")

    for i, row in enumerate(rows[:MAX_PEOPLE]):
        rank = _RANKS[i] if i < 3 else f"{p(i + 1)}."
        lines.append(f"{rank} <b>{html.escape(row['name'])}</b>")
        lines.append(_compact_line(row))
        lines.append("")

    hidden = len(rows) - MAX_PEOPLE
    if hidden > 0:
        lines.append(f"… و {p(hidden)} نفر دیگه")
        lines.append("")

    totals = {f: sum(r[f] for r in rows) for f in FIELDS}
    lines.append(_SEP)
    lines.append(f"👥 مجموع {p(len(rows))} نفر")
    lines.append(_compact_line(totals))
    lines.append("")
    lines.append(f"<i>{_LEGEND}</i>")
    return "\n".join(lines)


def build_person_text(name: str, row, total_mode: bool, since_iso: str = None) -> str:
    if total_mode:
        label = "آمار کل"
        if since_iso:
            label += f" · از {jalali_from_iso(since_iso)}"
    else:
        label = f"آمار امروز · {jalali_from_iso(_today_iso())}"

    lines = [f"👤 <b>{html.escape(name)}</b>", f"📅 {label}", ""]
    if not row:
        lines.append("📭 هنوز چیزی از این نفر ثبت نشده.")
        return "\n".join(lines)
    for f in FIELDS:
        lines.append(f"{ICONS[f]} {LABELS[f]}: <b>{fmt_int(row[f])}</b>")
    return "\n".join(lines)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, total_mode: bool):
    msg = update.effective_message
    chat = update.effective_chat
    if not chat or chat.type not in GROUP_TYPES:
        return

    day = None if total_mode else _today_iso()
    rows = query_people(chat.id, day)
    since = query_since(chat.id) if total_mode else None

    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if target and not target.is_bot:
        row = next((r for r in rows if r["user_id"] == target.id), None)
        name = (target.full_name or target.username or "بدون‌نام").strip()[:30]
        text = build_person_text(name, row, total_mode, since)
    else:
        text = build_group_text(rows, total_mode, since)

    await msg.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# نرخ‌ها (با کش) و ذخیره‌ی تاریخچه برای نمودار
# ---------------------------------------------------------------------------

_rate_cache = {}  # symbol -> (زمان, قیمت به تومان)


def _fetch_prices_blocking(want) -> dict:
    """قیمت دلار/طلا (tgju) و تتر (CoinGecko × نرخ دلار) رو به تومان برمی‌گردونه"""
    out = {}
    tgju = pc.fetch_tgju_data()
    usd_toman = pc.get_usd_to_toman_rate(tgju)
    if "dollar" in want:
        out["dollar"] = usd_toman
    if "gold" in want:
        out["gold"], _ = pc.get_fiat_gold_price(tgju, "geram18")
    if "usdt" in want:
        try:
            cg = pc.fetch_coingecko_data()
            out["usdt"], _ = pc.get_price_toman(cg, "usdt", usd_toman)
        except Exception as e:
            logger.warning(f"دریافت قیمت تتر از CoinGecko ناموفق بود: {e}")
            out["usdt"] = None
    now = time.time()
    for k, v in out.items():
        if v:
            _rate_cache[k] = (now, v)
    return out


async def get_rate(symbol: str):
    hit = _rate_cache.get(symbol)
    if hit and time.time() - hit[0] < RATE_CACHE_SECONDS:
        return hit[1]
    try:
        prices = await asyncio.to_thread(_fetch_prices_blocking, {symbol})
    except Exception as e:
        logger.warning(f"دریافت نرخ ناموفق بود: {e}")
        return None
    return prices.get(symbol)


async def record_prices_job(context: ContextTypes.DEFAULT_TYPE):
    """هر چند دقیقه یه‌بار قیمت‌ها رو ذخیره می‌کنه؛ نمودار از همین داده‌ها ساخته می‌شه"""
    try:
        prices = await asyncio.to_thread(_fetch_prices_blocking, {"dollar", "gold", "usdt"})
    except Exception as e:
        logger.warning(f"ذخیره‌ی قیمت ناموفق بود: {e}")
        return
    now = int(time.time())
    db = _db()
    with db:
        for symbol, price in prices.items():
            if price:
                db.execute("INSERT INTO price_history (symbol, ts, price) VALUES (?, ?, ?)",
                           (symbol, now, float(price)))
        db.execute("DELETE FROM price_history WHERE ts < ?", (now - PRICE_KEEP_DAYS * 86400,))


# ---------------------------------------------------------------------------
# تبدیل ارز
# ---------------------------------------------------------------------------

_AMOUNT = r"(\d+(?:\.\d+)?)(?: (هزار|میلیون|میلیارد))?"
_TO_TOMAN_RE = re.compile(rf"^{_AMOUNT} (دلار|تتر)(?: به تومان)?$")
_FROM_TOMAN_RE = re.compile(rf"^{_AMOUNT} تومان(?: به| در)? (دلار|تتر)$")
_MULT = {None: 1, "هزار": 1_000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000}
_CUR = {"دلار": ("dollar", "💵"), "تتر": ("usdt", "🪙")}
_MAX_AMOUNT = 1e13


def parse_conversion(text: str):
    """(جهت، مقدار، نام ارز) یا None. جهت: 'to_toman' یا 'from_toman'"""
    m = _TO_TOMAN_RE.match(text)
    if m:
        return "to_toman", float(m.group(1)) * _MULT[m.group(2)], m.group(3)
    m = _FROM_TOMAN_RE.match(text)
    if m:
        return "from_toman", float(m.group(1)) * _MULT[m.group(2)], m.group(3)
    return None


async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE, parsed):
    msg = update.effective_message
    chat = update.effective_chat
    direction, amount, cur_name = parsed
    symbol, emoji = _CUR[cur_name]
    if symbol == "dollar" and not _feature_ok(chat, "dollar"):
        return False

    if amount <= 0 or amount > _MAX_AMOUNT:
        return

    rate = await get_rate(symbol)
    if not rate:
        sent = await msg.reply_text("❌ نتونستم نرخ رو بگیرم، چند لحظه‌ی دیگه دوباره امتحان کن.")
        _schedule_delete(context, chat, [sent.message_id, msg.message_id])
        return

    if direction == "to_toman":
        head = f"{emoji} {fmt_num(amount)} {cur_name}"
        result = f"{fmt_int(amount * rate)} تومان"
    else:
        head = f"💰 {fmt_int(amount)} تومان"
        result = f"{fmt_num(amount / rate)} {cur_name}"

    text = (
        f"<b>{head}</b>\n\n"
        f"↔️ حدوداً <b>{result}</b>\n\n"
        f"📌 نرخ هر {cur_name}: {fmt_int(rate)} تومان"
    )
    sent = await msg.reply_text(text, parse_mode=ParseMode.HTML)
    _schedule_delete(context, chat, [sent.message_id, msg.message_id])


# ---------------------------------------------------------------------------
# نمودار
# ---------------------------------------------------------------------------

_CHART_RE = re.compile(r"^نمودار (دلار|طلا|تتر)(?: (امروز|روز|هفته|هفتگی|ماه|ماهانه))?$")
_CHART_SYMBOL = {"دلار": "dollar", "طلا": "gold", "تتر": "usdt"}
_CHART_PERIOD = {
    None: (1, "۲۴ ساعت اخیر"), "امروز": (1, "۲۴ ساعت اخیر"), "روز": (1, "۲۴ ساعت اخیر"),
    "هفته": (7, "۷ روز اخیر"), "هفتگی": (7, "۷ روز اخیر"),
    "ماه": (30, "۳۰ روز اخیر"), "ماهانه": (30, "۳۰ روز اخیر"),
}

_font_ready = False


def _setup_font():
    global _font_ready
    if _font_ready or not HAS_MPL:
        return
    _font_ready = True
    if os.path.exists(pc.FONT_PATH):
        try:
            font_manager.fontManager.addfont(pc.FONT_PATH)
            name = font_manager.FontProperties(fname=pc.FONT_PATH).get_name()
            matplotlib.rcParams["font.family"] = name
        except Exception as e:
            logger.warning(f"لود فونت نمودار ناموفق بود: {e}")


# پس‌زمینه‌ی نمودار: هر عکسی که تو پوشه‌ی assets با یکی از این اسم‌ها بذاری استفاده می‌شه.
# اگه هیچ‌کدوم نبود، همون پس‌زمینه‌ی کارت قیمت‌ها (price_card_bg.jpg) استفاده می‌شه.
CHART_BG_NAMES = ("chart_bg.jpg", "chart_bg.jpeg", "chart_bg.png")
CHART_W, CHART_H = 1200, 675
PANEL_MARGIN = 40


def _fit_background(bg: Image.Image, width: int, height: int) -> Image.Image:
    """عکس رو برش می‌زنه که کامل قاب رو پر کنه و یه لایه‌ی تیره‌ی نیمه‌شفاف روش می‌ندازه"""
    bg = bg.convert("RGB")
    src_w, src_h = bg.size
    target = width / height
    if src_w / src_h > target:
        new_w = int(src_h * target)
        left = (src_w - new_w) // 2
        bg = bg.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target)
        top = (src_h - new_h) // 2
        bg = bg.crop((0, top, src_w, top + new_h))
    bg = bg.resize((width, height), Image.LANCZOS)
    overlay = Image.new("RGBA", (width, height), (8, 4, 18, 110))
    return Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")


def _load_chart_background(width: int, height: int) -> Image.Image:
    assets = os.path.dirname(pc.FONT_PATH)
    for name in CHART_BG_NAMES:
        path = os.path.join(assets, name)
        if os.path.exists(path):
            try:
                return _fit_background(Image.open(path), width, height)
            except Exception as e:
                logger.warning(f"لود پس‌زمینه‌ی نمودار ({name}) ناموفق بود: {e}")
    return pc._load_background(width, height)


def render_chart(symbol: str, rows, period_days: int, period_label: str) -> io.BytesIO:
    _setup_font()

    # اگه نقطه‌ها خیلی زیاد بود، کم‌شون می‌کنیم که نمودار سنگین نشه
    if len(rows) > 700:
        step = len(rows) // 700 + 1
        rows = rows[::step] + [rows[-1]]

    times = [datetime.fromtimestamp(ts, TEHRAN) for ts, _ in rows]
    prices = [pr for _, pr in rows]
    lo, hi = min(prices), max(prices)
    pad = (hi - lo) * 0.18 or hi * 0.01
    y_lo, y_hi = lo - pad, hi + pad

    color = tuple(c / 255 for c in pc._coin_color(symbol))
    gold = (235 / 255, 180 / 255, 90 / 255)   # همون طلایی کارت قیمت‌ها
    soft = "#e6dccb"

    # نمودار روی زمینه‌ی شفاف کشیده می‌شه، بعد روی پس‌زمینه + پنل شیشه‌ای گذاشته می‌شه
    fig = Figure(figsize=(CHART_W / 100, CHART_H / 100), dpi=100, facecolor="none")
    ax = fig.add_axes([0.12, 0.12, 0.80, 0.50], facecolor="none")

    ax.plot(times, prices, color=color, linewidth=3, solid_capstyle="round")
    ax.fill_between(times, prices, y_lo, color=color, alpha=0.18)
    ax.scatter([times[-1]], [prices[-1]], color=color, s=80, zorder=5)
    ax.set_ylim(y_lo, y_hi)
    ax.margins(x=0.02)

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    if period_days <= 1:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TEHRAN))
    else:
        def _jal(v, _):
            d = mdates.num2date(v, tz=TEHRAN)
            _, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
            return f"{jm:02d}/{jd:02d}"
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(_jal))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7, tz=TEHRAN))

    ax.tick_params(colors=soft, labelsize=12, length=0)
    ax.grid(True, color="white", alpha=0.10, linewidth=1)
    for spine in ax.spines.values():
        spine.set_visible(False)

    first, last = prices[0], prices[-1]
    change = (last - first) / first * 100 if first else 0.0
    change_color = "#5ac882" if change >= 0 else "#ff5a5a"
    sign = "+" if change >= 0 else ""

    name = pc._tr_name(symbol, "fa")
    fig.text(0.5, 0.865, pc._fa(name), ha="center", va="center", fontsize=30, color="white")
    fig.text(0.5, 0.808, pc._fa(period_label), ha="center", va="center", fontsize=15, color=soft)
    fig.text(0.5, 0.748, pc._fa(f"{int(last):,} تومان"), ha="center", va="center",
             fontsize=25, color=gold)
    fig.text(0.5, 0.690, pc._fa(f"{sign}{change:.2f}٪"), ha="center", va="center",
             fontsize=16, color=change_color)

    chart_buf = io.BytesIO()
    fig.savefig(chart_buf, format="png", transparent=True)
    chart_buf.seek(0)
    chart = Image.open(chart_buf).convert("RGBA")
    if chart.size != (CHART_W, CHART_H):
        chart = chart.resize((CHART_W, CHART_H), Image.LANCZOS)

    base = _load_chart_background(CHART_W, CHART_H)
    base = pc._glass_panel(base, PANEL_MARGIN, PANEL_MARGIN, CHART_W - PANEL_MARGIN, CHART_H - PANEL_MARGIN)
    final = Image.alpha_composite(base.convert("RGBA"), chart).convert("RGB")

    buf = io.BytesIO()
    final.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "chart.png"
    return buf


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, fa_symbol: str, fa_period):
    msg = update.effective_message
    chat = update.effective_chat
    symbol = _CHART_SYMBOL[fa_symbol]
    days, label = _CHART_PERIOD[fa_period]
    if symbol == "dollar" and not _feature_ok(chat, "dollar"):
        return False

    async def _reply_and_clean(text):
        sent = await msg.reply_text(text)
        _schedule_delete(context, chat, [sent.message_id, msg.message_id])

    if not HAS_MPL:
        await _reply_and_clean("❌ کتابخونه‌ی matplotlib نصب نیست، نمودار کار نمی‌کنه.")
        return

    since_ts = int(time.time()) - days * 86400
    rows = _db().execute(
        "SELECT ts, price FROM price_history WHERE symbol = ? AND ts >= ? ORDER BY ts",
        (symbol, since_ts),
    ).fetchall()

    if len(rows) < 3:
        await _reply_and_clean("⏳ هنوز داده‌ی کافی برای نمودار جمع نشده، چند دقیقه‌ی دیگه دوباره امتحان کن.")
        return

    try:
        buf = await asyncio.to_thread(render_chart, symbol, rows, days, label)
    except Exception as e:
        logger.exception("ساخت نمودار ناموفق بود")
        await _reply_and_clean(f"❌ نتونستم نمودار رو بسازم.\n{e}")
        return

    name = pc._tr_name(symbol, "fa")
    caption = f"📈 نمودار {name} · {label}\n💰 آخرین قیمت: {fmt_int(rows[-1][1])} تومان"

    # اگه داده‌ی جمع‌شده از بازه‌ی خواسته‌شده کمتره، صادقانه بگیم
    covered_hours = (rows[-1][0] - rows[0][0]) / 3600
    if covered_hours < days * 24 * 0.9:
        if covered_hours < 48:
            caption += f"\n\n📌 فعلاً فقط داده‌ی {p(int(covered_hours) or 1)} ساعت اخیر ثبت شده."
        else:
            caption += f"\n\n📌 فعلاً فقط داده‌ی {p(int(covered_hours // 24))} روز اخیر ثبت شده."

    sent = await msg.reply_photo(photo=buf, caption=caption)
    _schedule_delete(context, chat, [sent.message_id, msg.message_id])


# ---------------------------------------------------------------------------
# مسیریابی پیام‌های متنی
# ---------------------------------------------------------------------------

_STATS_TODAY = {"آمار", "امار"}
_STATS_TOTAL = {"آمار کل", "امار کل"}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگه پیام یکی از دستورهای این فایل بود انجامش می‌ده و True برمی‌گردونه، وگرنه False"""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not msg.text or len(msg.text) > 80:
        return False
    text = _norm(msg.text)
    in_group = bool(chat and chat.type in GROUP_TYPES)

    if text in _STATS_TODAY or text in _STATS_TOTAL:
        if not in_group:          # آمار فقط برای گروه‌هاست
            return False
        await cmd_stats(update, context, total_mode=text in _STATS_TOTAL)
        return True

    m = _CHART_RE.match(text)
    if m:
        return await cmd_chart(update, context, m.group(1), m.group(2)) is not False

    parsed = parse_conversion(text)
    if parsed:
        return await cmd_convert(update, context, parsed) is not False

    return False


async def _group_text_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_text(update, context)


# ---------------------------------------------------------------------------
# نصب روی ربات
# ---------------------------------------------------------------------------

def register(application):
    """تو main.py بعد از ساختن app صدا بزن: extras.register(app)

    نکته: دستورهای پی‌وی (تبدیل ارز و نمودار) از تو guarded_private_text صدا زده می‌شن
    (extras.handle_text)، چون اون تابع پیام‌های ناشناخته‌ی پی‌وی رو پاک می‌کنه.
    """
    _db()  # ساخت جدول‌ها

    # شمارش پیام‌های گروه: گروه شماره‌ی مخصوص خودش (-5) تا نه گیت خاموشی (گروه -1) جلوش رو بگیره
    # و نه هندلر دیگه‌ای. تو PTB تو هر گروه فقط اولین هندلرِ مچ‌شده اجرا می‌شه.
    application.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE & filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
            count_message,
        ),
        group=-5,
    )
    # دستورهای گروه (آمار، تبدیل، نمودار) تو گروه 1
    application.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE & filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            _group_text_entry,
        ),
        group=1,
    )

    if application.job_queue:
        application.job_queue.run_repeating(record_prices_job, interval=PRICE_SAMPLE_INTERVAL, first=15)
    else:
        logger.warning("job_queue نصب نیست؛ قیمت‌ها برای نمودار ذخیره نمی‌شن. "
                       "python-telegram-bot[job-queue] رو نصب کن.")
