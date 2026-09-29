#!/usr/bin/env python3
"""
دانلودر همه‌کاره با استفاده از yt-dlp
از بیش از ۱۸۰۰ سایت پشتیبانی می‌کنه (یوتیوب، اینستاگرام، ساندکلاود، تیک‌تاک، توییتر/X،
ویمیو، توییچ، فیسبوک، پینترست و خیلی سایت‌های دیگه)

نصب پیش‌نیاز (یک‌بار کافیه):
    pip install yt-dlp

اجرا:
    python downloader.py
"""

import os
import sys

try:
    import yt_dlp
except ImportError:
    print("پکیج yt-dlp نصب نیست.")
    print("این دستور رو اجرا کن و دوباره امتحان کن:")
    print("    pip install yt-dlp")
    sys.exit(1)


def get_download_folder():
    """پوشه‌ی Downloads رو پیدا می‌کنه، وگرنه یه پوشه به اسم downloads می‌سازه."""
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    if not os.path.isdir(downloads):
        downloads = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads, exist_ok=True)
    return downloads


def progress_hook(d):
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "").strip()
        speed = d.get("_speed_str", "").strip()
        print(f"\rدر حال دانلود... {percent}  سرعت: {speed}", end="", flush=True)
    elif d["status"] == "finished":
        print("\nدانلود تموم شد، در حال پردازش نهایی...")


def download(url: str, audio_only: bool, out_dir: str):
    ydl_opts = {
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "noplaylist": False,   # اگه لینک پلی‌لیست بود کل پلی‌لیست دانلود میشه
        "quiet": True,
        "no_warnings": True,
    }

    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main():
    print("=" * 50)
    print("  دانلودر همه‌کاره (yt-dlp)")
    print("  پشتیبانی از یوتیوب + ۱۸۰۰ سایت دیگه")
    print("=" * 50)

    out_dir = get_download_folder()
    print(f"مسیر ذخیره فایل‌ها: {out_dir}\n")

    while True:
        url = input("لینک رو وارد کن (یا 'خروج' برای پایان): ").strip()
        if url.lower() in ("خروج", "exit", "quit", "q"):
            print("خدانگهدار!")
            break
        if not url:
            continue

        choice = input("فقط صدا (mp3) بگیرم؟ (y/n): ").strip().lower()
        audio_only = choice in ("y", "yes", "بله", "آره")

        try:
            download(url, audio_only, out_dir)
            print("✅ دانلود با موفقیت انجام شد!\n")
        except Exception as e:
            print(f"❌ خطا در دانلود: {e}\n")


if __name__ == "__main__":
    main()
