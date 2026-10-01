# -*- coding: utf-8 -*-
"""
دانلود و ارسال خودکار مدیا از روی لینک — با yt-dlp، که حدود ۱۸۰۰ سایت رو
پشتیبانی می‌کنه (یوتیوب، اینستاگرام، توییتر/X، تیک‌تاک، پینترست، ساندکلاود
و خیلی سایت‌های دیگه)، نه فقط اینستاگرام.

هر لینکی که تو پی‌وی یا گروه فرستاده بشه، خودکار دانلود و فرستاده می‌شه.
اگه پست چندتا عکس/ویدیو (کاروسل) داشته باشه، همه‌شون با هم (تا سقف ۱۰ تا،
محدودیت خودِ تلگرام) فرستاده می‌شن.

نصب لازم روی سرور:
    pip install yt-dlp
اگه بعضی لینک‌ها (مخصوصاً اینستاگرام) با خطای لاگین/محدودیت مواجه شدن، یه
فایل کوکیِ خروجی‌گرفته‌شده از یه اکانت لاگین‌شده رو با اسم
assets/instagram_cookies.txt کنار پروژه بذار؛ فقط برای لینک‌های اینستاگرام
خودکار استفاده می‌شه.

دستور «دانلودر» تو گروه: یه یادآوریِ خودپاک‌شونده‌ست. اگه کسی بنویسه «دانلودر»،
ربات می‌گه لینک رو بفرست. اگه لینک بده، مدیا دانلود و فرستاده می‌شه و خودِ
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

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo, InputMediaAudio,
)
from telegram.ext import ContextTypes

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

logger = logging.getLogger(__name__)

# قبلاً فقط لینک‌های اینستاگرام تشخیص داده می‌شدن. الان هر لینک http/https
# عادی قبول می‌شه و به yt-dlp سپرده می‌شه که تصمیم بگیره از اون سایت
# پشتیبانی می‌کنه یا نه (اگه نکنه، خودِ yt-dlp خطای «unsupported url» می‌ده
# که پایین‌تر مدیریت شده).
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# لینک‌هایی که اصلاً نباید به‌عنوان «لینک دانلود» در نظر گرفته بشن - مخصوصاً
# لینک‌های خودِ تلگرام (مثل t.me/...، که خیلی وقت‌ها برای اشتراک گروه/کانال/
# پیام بین کاربرا رد و بدل می‌شه و ربطی به دانلود مدیا نداره)
EXCLUDED_DOMAINS = ("t.me", "telegram.me", "telegram.org", "telegram.dog")


def _is_excluded_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        host = host.split("@")[-1]  # اگه یوزرنیم/پسورد تو لینک بود
        host = host.split(":")[0]   # پورت رو حذف کن
        return any(host == d or host.endswith("." + d) for d in EXCLUDED_DOMAINS)
    except Exception:
        return False


MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # محدودیت آپلود فایل برای ربات‌های تلگرام
MAX_MEDIA_GROUP = 10                   # سقف تلگرام برای هر آلبوم/مدیاگروپ
DOWNLOADER_WAIT_TIMEOUT = 180          # ثانیه؛ بعدش یادآوری خودکار پاک می‌شه
GROUP_TYPES = ("group", "supergroup")

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "mkv", "webm"}
AUDIO_EXTENSIONS = {"mp3", "m4a", "opus", "ogg", "wav"}

COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "instagram_cookies.txt")

# آیدی پیام «لینک رو بفرست» تو پی‌وی، از همون سیستم مشترک پنل تو start.py
# (panel_msg_{chat_id} تو دیتابیس) استفاده می‌شه تا با بقیه‌ی بخش‌های ربات
# هماهنگ بمونه و باعث دوتا شدن پنل نشه.


def _video_back_keyboard(link_message_id: int):
    """دکمه‌ی زیر مدیا تو پی‌وی: با زدنش، مدیا + پیام لینک پاک می‌شن و برمی‌گرده به پنل اصلی"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به پنل اصلی", callback_data=f"dl_back:{link_message_id}")]
    ])


def find_instagram_link(text: str):
    """
    نگه‌داشته شده برای سازگاری با کدهای قدیمی، ولی الان دیگه فقط مخصوص
    اینستاگرام نیست: هر لینک http/https رو پیدا می‌کنه.
    """
    if not text:
        return None
    for m in URL_RE.finditer(text):
        url = m.group(0)
        if not _is_excluded_url(url):
            return url
    return None


def _is_photo_path(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in PHOTO_EXTENSIONS


def _is_audio_path(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in AUDIO_EXTENSIONS


def _download_blocking(url: str, out_dir: str):
    """
    دانلود مسدودکننده با yt-dlp؛ باید تو یه ترد جدا صدا زده بشه.
    اگه پست/صفحه تک‌آیتمی باشه، یه فایل برمی‌گردونه؛ اگه کاروسل (چند
    عکس/ویدیو، مثلاً پست چندتایی اینستاگرام) باشه، همه‌ی آیتم‌ها رو
    دانلود و لیست مسیرهاشون رو برمی‌گردونه.

    این تابع مخصوص یه سایت خاص نیست - از هر لینکی که yt-dlp پشتیبانی
    کنه (حدود ۱۸۰۰ سایت: یوتیوب، توییتر/X، تیک‌تاک، پینترست، ساندکلاود،
    و غیره) استفاده می‌کنه. برای ویدیوها، فرمت mp4 (سازگارترین فرمت با
    پخش‌کننده‌ی تلگرام) در اولویته؛ برای ادغام صدا/تصویر جدا، ffmpeg
    روی سرور لازمه.
    """
    out_tmpl = os.path.join(out_dir, "item_%(playlist_index,autonumber)02d.%(ext)s")
    opts = {
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,   # اجازه بده کل کاروسل/پلی‌لیست دانلود بشه، نه فقط اولین آیتم
        "playlistend": MAX_MEDIA_GROUP,  # اگه لینک یه پلی‌لیست بزرگ بود، فقط تا سقف آلبوم تلگرام دانلود کن
        # فرمت رو اجباری به mp4/merge نمی‌کنیم چون این محدودیت مخصوص ویدیوعه و
        # باعث می‌شد آیتم‌های فقط-عکسی (بدون فرمت ویدیویی) دانلود نشن. با
        # گذاشتن mp4 به‌عنوان اولویت (نه اجبار)، هم عکس هم ویدیو درست میان.
        "format": "bv*+ba/b/bv*+ba[ext=m4a]/best",
        "format_sort": ["ext:mp4:m4a"],
        "max_filesize": MAX_UPLOAD_BYTES,
        "socket_timeout": 30,
        "retries": 2,
        "ignoreerrors": True,  # اگه یه آیتم از کاروسل (مثلاً یه ویدیو خاص) خطا داد،
                                 # بقیه‌ی آیتم‌ها (مثلاً عکس‌ها) همچنان دانلود بشن
    }
    # کوکی فقط برای لینک‌های اینستاگرام استفاده می‌شه (چون فایل کوکی
    # مخصوص همون سایته و برای بقیه‌ی سایت‌ها ربطی نداره)
    if ("instagram.com" in url.lower() or "instagr.am" in url.lower()) and os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH

    paths = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        entries = info.get("entries") if isinstance(info, dict) else None
        if entries:
            for entry in entries:
                if not entry:
                    continue
                try:
                    p = ydl.prepare_filename(entry)
                except Exception:
                    continue
                if os.path.exists(p):
                    paths.append(p)
        else:
            p = ydl.prepare_filename(info)
            if os.path.exists(p):
                paths.append(p)

    # اگه به هر دلیلی prepare_filename مسیر درست رو نداد، هرچی تو پوشه‌ی
    # موقت واقعاً دانلود شده رو (به ترتیب اسم) به‌عنوان جایگزین برمی‌داریم
    if not paths:
        for name in sorted(os.listdir(out_dir)):
            paths.append(os.path.join(out_dir, name))

    return paths


async def download_instagram_media(url: str):
    """
    دانلود همه‌ی آیتم‌های یه لینک اینستاگرام (عکس/ویدیو/کاروسل) تو یه پوشه‌ی موقت.
    خروجی: (paths, error). اگه error خالی بود یعنی موفق و paths لیست غیرخالیه؛
    فایل‌ها باید بعداً توسط caller (با _cleanup_files) پاک بشن.
    """
    if not HAS_YTDLP:
        return None, "کتابخونه‌ی yt-dlp روی سرور نصب نیست."

    tmp_dir = tempfile.mkdtemp(prefix="igdl_")
    try:
        paths = await asyncio.to_thread(_download_blocking, url, tmp_dir)
        if not paths:
            return None, "دانلود ناموفق بود."

        # نکته‌ی مهم: محدودیت آپلود تلگرام (۵۰ مگابایت) مال هر فایل به‌تنهایی‌ه،
        # نه مجموع فایل‌ها. قبلاً اینجا اشتباهاً مجموع رو با ۵۰×۱۰=۵۰۰ مگابایت
        # مقایسه می‌کرد، برای همین یه ویدیوی تکیِ ۲۰۰ مگابایتی قبول می‌شد ولی
        # موقع ارسال با خطای تلگرام رد می‌شد. الان هر فایل جدا چک می‌شه.
        oversized = [p for p in paths if os.path.exists(p) and os.path.getsize(p) > MAX_UPLOAD_BYTES]
        if oversized:
            for p in oversized:
                _cleanup_file(p)
            paths = [p for p in paths if p not in oversized]
            if not paths:
                return None, "حجم فایل بیشتر از حد مجاز ارسال ربات (۵۰ مگابایت) است."

        # سقف تلگرام برای هر آلبوم ۱۰ تا آیتمه
        if len(paths) > MAX_MEDIA_GROUP:
            for extra in paths[MAX_MEDIA_GROUP:]:
                _cleanup_file(extra)
            paths = paths[:MAX_MEDIA_GROUP]

        return paths, None
    except Exception as e:
        msg = str(e).lower()
        try:
            for f in os.listdir(tmp_dir):
                os.remove(os.path.join(tmp_dir, f))
            os.rmdir(tmp_dir)
        except Exception:
            pass
        if "private" in msg:
            return None, "این لینک خصوصیه و قابل دانلود نیست."
        if "login" in msg or "rate-limit" in msg or "429" in msg:
            return None, "سایت فعلاً درخواست رو رد کرد (احتمالاً نیاز به کوکی لاگین‌شده داره)."
        if "unsupported url" in msg:
            return None, "این سایت یا لینک پشتیبانی نمی‌شه."
        logger.warning(f"خطای دانلود: {e}")
        return None, "دانلود این لینک ناموفق بود."


def _cleanup_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _cleanup_files(paths):
    if not paths:
        return
    folder = os.path.dirname(paths[0])
    for p in paths:
        _cleanup_file(p)
    try:
        if folder and os.path.exists(folder) and not os.listdir(folder):
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


async def _send_media(message, paths, caption, reply_markup, has_spoiler=False):
    """
    یه فایل -> reply_photo/reply_video/reply_audio (بسته به نوعش).
    چند فایل -> reply_media_group (آلبوم)، بعدش اگه reply_markup لازم بود
    (چون تلگرام رو خودِ آلبوم دکمه پشتیبانی نمی‌کنه) جدا زیرش فرستاده می‌شه.
    """
    """
    خروجی: لیستی از همه‌ی پیام‌هایی که فرستاده شده (نه فقط اولی)، تا بشه
    بعداً همه‌شون رو برای پاک‌سازیِ خودکار ردیابی کرد.
    """
    if len(paths) == 1:
        path = paths[0]
        with open(path, "rb") as f:
            if _is_photo_path(path):
                sent = await message.reply_photo(
                    photo=f, caption=caption, reply_markup=reply_markup, has_spoiler=has_spoiler
                )
            elif _is_audio_path(path):
                sent = await message.reply_audio(audio=f, caption=caption, reply_markup=reply_markup)
            else:
                sent = await message.reply_video(
                    video=f, caption=caption, reply_markup=reply_markup, has_spoiler=has_spoiler
                )
        return [sent]

    files = [open(p, "rb") for p in paths]
    try:
        media = []
        for i, (path, f) in enumerate(zip(paths, files)):
            kwargs = {"caption": caption} if i == 0 else {}
            if _is_photo_path(path):
                media.append(InputMediaPhoto(f, has_spoiler=has_spoiler, **kwargs))
            elif _is_audio_path(path):
                media.append(InputMediaAudio(f, **kwargs))
            else:
                media.append(InputMediaVideo(f, has_spoiler=has_spoiler, **kwargs))
        sent_list = await message.reply_media_group(media=media)
        all_sent = list(sent_list) if sent_list else []
        if reply_markup:
            btn_msg = await message.reply_text("مدیریت این پست:", reply_markup=reply_markup)
            all_sent.append(btn_msg)
        return all_sent
    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass


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

    is_private = not (chat and chat.type in GROUP_TYPES)

    if not is_private:
        if not await _feature_enabled(chat):
            return False
    else:
        if not context.user_data.get("downloader_mode"):
            return False
        # پیام «لینک رو بفرست» دیگه لازم نیست، همین اولین لینک که رسید پاکش می‌کنیم
        # (از همون سیستم مشترک پنل تو start.py استفاده می‌کنیم)
        from start import _delete_old_panel
        await _delete_old_panel(context, chat.id)
        # این بخش طوری طراحی شده که تو پی‌وی مثل یه تک‌صفحه‌ای بمونه: با رسیدن
        # هر لینک جدید، هر چی پیامِ نتیجه/خطای دانلودر از قبل مونده (نه فقط
        # پنل بالایی) هم پاک می‌شه که پیام‌های قدیمی روی هم تلنبار نشن.
        old_result_ids = context.user_data.pop("dl_last_result_msgs", None) or []
        for mid in old_result_ids:
            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=mid)
            except Exception:
                pass

    back_kb = _video_back_keyboard(message.message_id) if is_private else None

    status = await message.reply_text("⏳ در حال دانلود...")
    paths, error = await download_instagram_media(url)

    result_ids = []
    if error:
        try:
            await status.edit_text(f"❌ {error}", reply_markup=back_kb)
            result_ids.append(status.message_id)
        except Exception:
            pass
    else:
        try:
            await status.delete()
        except Exception:
            pass
        try:
            sent_msgs = await _send_media(message, paths, "📥 دانلود شد", back_kb)
            result_ids.extend(m.message_id for m in sent_msgs if m)
        except Exception as e:
            logger.warning(f"ارسال مدیای اینستاگرام ناموفق بود: {e}")
            try:
                err_msg = await message.reply_text(
                    "❌ مدیا دانلود شد ولی ارسالش ناموفق بود (احتمالاً حجم بالاست).",
                    reply_markup=back_kb
                )
                result_ids.append(err_msg.message_id)
            except Exception:
                pass
        finally:
            _cleanup_files(paths)

    if is_private and result_ids:
        context.user_data["dl_last_result_msgs"] = result_ids

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

    prompt = await message.reply_text("📥 لینک مورد نظر رو بفرست (یوتیوب، اینستاگرام، توییتر، تیک‌تاک و خیلی سایت‌های دیگه).")
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
    "📥 دانلودر\n\n"
    "لینک مورد نظرت رو همین‌جا بفرست (یوتیوب، اینستاگرام، توییتر/X، تیک‌تاک، "
    "پینترست، ساندکلاود و خیلی سایت‌های دیگه)، خودم دانلودش می‌کنم و برات "
    "می‌فرستم (اگه پست چند عکس/ویدیو داشت، همه‌شون با هم فرستاده می‌شن).\n\n"
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
    # همون پیام (که الان ویرایش شد) به‌عنوان «پنل فعلی» تو سیستم مشترک ثبت می‌شه
    from start import _remember_panel
    _remember_panel(query.message.chat_id, query.message.message_id)


async def private_downloader_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی تو پی‌وی به‌جای زدن دکمه، مستقیم کلمه‌ی «دانلودر» رو تایپ کنه"""
    from start import _delete_old_panel, _remember_panel
    chat = update.effective_chat
    context.user_data["downloader_mode"] = True
    await _delete_old_panel(context, chat.id)
    sent = await update.effective_message.reply_text(DOWNLOADER_PANEL_TEXT, reply_markup=_downloader_keyboard())
    _remember_panel(chat.id, sent.message_id)


async def handle_downloader_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    کلیک روی دکمه‌ی «⬅️ بازگشت به پنل اصلی» که زیر مدیا (یا پیام خطا) نشسته:
    خودِ اون پیام + پیام لینکی که کاربر فرستاده بود پاک می‌شن، و یه پنل اصلی تازه فرستاده می‌شه.
    """
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    try:
        link_message_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        link_message_id = None

    # پاک کردن خودِ مدیا/پیام خطا
    try:
        await query.message.delete()
    except Exception:
        pass
    # پاک کردن پیام لینکی که خودِ کاربر فرستاده بود
    if link_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=link_message_id)
        except Exception:
            pass

    context.user_data["downloader_mode"] = False

    # فرستادن یه پنل اصلی تازه (پنل قبلی، اگه هنوز جایی مونده باشه، پاک می‌شه)
    from start import build_start_keyboard, START_TEXT, _delete_old_panel, _remember_panel
    await _delete_old_panel(context, chat_id)
    bot_username = (await context.bot.get_me()).username
    sent = await context.bot.send_message(
        chat_id, START_TEXT,
        reply_markup=build_start_keyboard(query.from_user.id, bot_username)
    )
    _remember_panel(chat_id, sent.message_id)
