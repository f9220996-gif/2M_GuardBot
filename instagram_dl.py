# -*- coding: utf-8 -*-
"""
دانلود و ارسال خودکار ویدیوی اینستاگرام از روی لینک.

هر لینک اینستاگرامی (ریلز، پست، IGTV) که تو پی‌وی یا گروه فرستاده بشه،
خودکار دانلود و به‌صورت ویدیو فرستاده می‌شه. فقط اینستاگرام پشتیبانی می‌شه.

نصب لازم روی سرور:
    pip install yt-dlp
اگه بعضی لینک‌ها با خطای لاگین/محدودیت مواجه شدن (چیزی که برای اینستاگرام
معمول شده)، یه فایل کوکیِ خروجی‌گرفته‌شده از یه اکانت لاگین‌شده رو با اسم
assets/instagram_cookies.txt کنار پروژه بذار؛ خودکار استفاده می‌شه.

دستور «دانلودر» تو گروه: یه یادآوریِ خودپاک‌شونده‌ست. اگه کسی بنویسه «دانلودر»،
ربات می‌گه لینک رو بفرست. اگه لینک بده، ویدیو دانلود و فرستاده می‌شه و خودِ
پیام «دانلودر» + یادآوریِ ربات پاک می‌شن که گروه شلوغ نمونه. اگه یادش بره و
لینک نفرسته، بعد از چند دقیقه همون دو پیام خودکار پاک می‌شن.

نکته: تشخیص خودکار لینک همیشه فعاله (نیازی به دستور «دانلودر» نیست) -
دستور «دانلودر» فقط یه یادآوریِ تمیزِ اضافیه.
"""

import asyncio
import logging
import os
import re
import tempfile
import time

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

logger = logging.getLogger(__name__)

INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+[^\s\u200c]*",
    re.IGNORECASE,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # محدودیت آپلود فایل برای ربات‌های تلگرام
DOWNLOADER_WAIT_TIMEOUT = 180          # ثانیه؛ بعدش یادآوری خودکار پاک می‌شه
GROUP_TYPES = ("group", "supergroup")

COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "instagram_cookies.txt")


def find_instagram_link(text: str):
    if not text:
        return None
    m = INSTAGRAM_RE.search(text)
    return m.group(0) if m else None


def _download_blocking(url: str, out_dir: str):
    """دانلود مسدودکننده با yt-dlp؛ باید تو یه ترد جدا صدا زده بشه"""
    out_tmpl = os.path.join(out_dir, "video.%(ext)s")
    opts = {
        "outtmpl": out_tmpl,
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": MAX_UPLOAD_BYTES,
        "socket_timeout": 30,
        "retries": 2,
    }
    if os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        return path


async def download_instagram_video(url: str):
    """
    دانلود ویدیو تو یه پوشه‌ی موقت.
    خروجی: (path, error). اگه error خالی بود یعنی موفق؛ فایل باید بعداً
    توسط caller (با _cleanup_file) پاک بشه.
    """
    if not HAS_YTDLP:
        return None, "کتابخونه‌ی yt-dlp روی سرور نصب نیست."

    tmp_dir = tempfile.mkdtemp(prefix="igdl_")
    try:
        path = await asyncio.to_thread(_download_blocking, url, tmp_dir)
        if not path or not os.path.exists(path):
            return None, "دانلود ناموفق بود."
        if os.path.getsize(path) > MAX_UPLOAD_BYTES:
            _cleanup_file(path)
            return None, "حجم ویدیو بیشتر از حد مجاز ارسال ربات (۵۰ مگابایت) است."
        return path, None
    except Exception as e:
        msg = str(e).lower()
        try:
            for f in os.listdir(tmp_dir):
                os.remove(os.path.join(tmp_dir, f))
            os.rmdir(tmp_dir)
        except Exception:
            pass
        if "private" in msg:
            return None, "این پست خصوصیه و قابل دانلود نیست."
        if "login" in msg or "rate-limit" in msg or "429" in msg:
            return None, "اینستاگرام فعلاً درخواست رو رد کرد (نیاز به کوکی لاگین‌شده دارد)."
        if "unsupported url" in msg or "no video" in msg:
            return None, "این لینک معتبر یا ویدیودار نیست."
        logger.warning(f"خطای دانلود اینستاگرام: {e}")
        return None, "دانلود این لینک ناموفق بود."


def _cleanup_file(path):
    try:
        if path and os.path.exists(path):
            folder = os.path.dirname(path)
            os.remove(path)
            if not os.listdir(folder):
                os.rmdir(folder)
    except Exception:
        pass


async def _feature_enabled(chat) -> bool:
    if not chat or chat.type not in GROUP_TYPES:
        return True
    try:
        import database as db
        return db.is_feature_enabled(chat.id, "instagram_dl")
    except Exception:
        return True


# ---------------------------------------------------------------------------
# تشخیص خودکار لینک (هم تو پی‌وی هم گروه)
# ---------------------------------------------------------------------------

async def try_handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    اگه پیام لینک اینستاگرام داشت، دانلود و ارسال می‌کنه و True برمی‌گردونه.
    تو گروه: همیشه فعاله (اگه قابلیتش خاموش نشده باشه).
    تو پی‌وی: فقط وقتی کاربر از دکمه‌ی «📥 دانلودر اینستاگرام» وارد اون بخش شده باشه
    (یعنی حالت downloader_mode روشن باشه)، وگرنه لینک نادیده گرفته می‌شه تا پی‌وی
    شلوغ نشه و همه‌چیز فقط داخل همون بخش مخصوص اتفاق بیفته.
    """
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.text:
        return False

    url = find_instagram_link(message.text)
    if not url:
        return False

    if chat and chat.type in GROUP_TYPES:
        if not await _feature_enabled(chat):
            return False
    else:
        if not context.user_data.get("downloader_mode"):
            return False

    status = await message.reply_text("⏳ در حال دانلود ویدیو...")
    path, error = await download_instagram_video(url)

    if error:
        try:
            await status.edit_text(f"❌ {error}")
        except Exception:
            pass
    else:
        try:
            with open(path, "rb") as f:
                await message.reply_video(video=f, caption="📥 دانلود شد")
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"ارسال ویدیوی اینستاگرام ناموفق بود: {e}")
            try:
                await status.edit_text("❌ ویدیو دانلود شد ولی ارسالش ناموفق بود (احتمالاً حجم بالاست).")
            except Exception:
                pass
        finally:
            _cleanup_file(path)

    await _finish_wait_cleanup(update, context)
    return True


# ---------------------------------------------------------------------------
# دستور «دانلودر» تو گروه: یادآوریِ خودپاک‌شونده
# ---------------------------------------------------------------------------

def _wait_store(context):
    return context.chat_data.setdefault("dl_wait", {})


async def _cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """بعد از تایم‌اوت، اگه کاربر لینک نفرستاده باشه، پیام دستور + یادآوری رو پاک می‌کنه"""
    chat_id, user_id, trigger_id, prompt_id = context.job.data
    chat_data = context.application.chat_data.get(chat_id, {})
    wait = chat_data.get("dl_wait", {})
    entry = wait.get(user_id)
    # فقط اگه هنوز همون درخواستِ منتظره (یعنی جواب داده نشده)، پاک کن
    if entry and entry.get("trigger_id") == trigger_id:
        wait.pop(user_id, None)
        for mid in (trigger_id, prompt_id):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass


async def cmd_downloader_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not await _feature_enabled(chat):
        return

    prompt = await message.reply_text("📥 لینک ویدیوی اینستاگرام رو بفرست.")
    wait = _wait_store(context)
    wait[user.id] = {
        "trigger_id": message.message_id,
        "prompt_id": prompt.message_id,
        "created_at": time.time(),
    }

    if context.job_queue:
        context.job_queue.run_once(
            _cleanup_job, DOWNLOADER_WAIT_TIMEOUT,
            chat_id=chat.id,
            data=(chat.id, user.id, message.message_id, prompt.message_id),
        )


async def _finish_wait_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگه این کاربر منتظر لینک بود، پیام دستور «دانلودر» + یادآوری ربات رو پاک می‌کنه"""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in GROUP_TYPES or not user:
        return
    wait = _wait_store(context)
    entry = wait.pop(user.id, None)
    if not entry:
        return
    for mid in (entry["trigger_id"], entry["prompt_id"]):
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=mid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# پنل دانلودر تو پی‌وی: یه بخش جدا که با کلیک روش فعال می‌شه.
# قبل از ورود به این بخش، لینک‌ها تو پی‌وی نادیده گرفته می‌شن (بالا چک شد)
# تا پنل اصلی و بقیه‌ی پی‌وی شلوغ نمونه؛ همه‌چیز فقط اینجا اتفاق می‌افته.
# ---------------------------------------------------------------------------

DOWNLOADER_PANEL_TEXT = (
    "📥 دانلودر اینستاگرام\n\n"
    "لینک ویدیوی اینستاگرام (ریلز، پست یا IGTV) رو همین‌جا بفرست، "
    "خودم دانلودش می‌کنم و برات می‌فرستم.\n\n"
    "می‌تونی چند تا لینک پشت‌سرهم بفرستی. برای خروج از این بخش، دکمه‌ی زیر رو بزن."
)


def _downloader_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به پنل اصلی", callback_data="start_menu")]
    ])


async def open_downloader_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کلیک روی دکمه‌ی «📥 دانلودر اینستاگرام» تو پنل اصلی پی‌وی"""
    query = update.callback_query
    await query.answer()
    context.user_data["downloader_mode"] = True
    await query.edit_message_text(DOWNLOADER_PANEL_TEXT, reply_markup=_downloader_keyboard())


async def private_downloader_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی تو پی‌وی به‌جای زدن دکمه، مستقیم کلمه‌ی «دانلودر» رو تایپ کنه"""
    context.user_data["downloader_mode"] = True
    await update.effective_message.reply_text(DOWNLOADER_PANEL_TEXT, reply_markup=_downloader_keyboard())
