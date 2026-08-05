# -*- coding: utf-8 -*-
"""
لایه دیتابیس ربات (SQLite)
همه‌ی عملیات خواندن/نوشتن اطلاعات گروه‌ها، بن‌شده‌ها، سکوت‌ها، اخطارها،
لیست سیاه گیف/استیکر و تنظیمات ربات از همین‌جا انجام می‌شود.
"""

import sqlite3
import time
import json
from contextlib import contextmanager

from config import DB_PATH, DEFAULT_BAD_WORDS, DEFAULT_WARNING_TEXTS, DEFAULT_SHUTDOWN_MESSAGE


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """ساخت جدول‌ها در اولین اجرا"""
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            added_by_user_id INTEGER,
            added_by_username TEXT,
            is_locked INTEGER DEFAULT 0,
            lock_until REAL,          -- زمان یونیکس برای باز شدن خودکار، NULL یعنی قفل دائم
            is_active INTEGER DEFAULT 1  -- روشن/خاموش بودن ربات فقط برای این گروه
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            reason TEXT,
            level INTEGER,       -- شماره اخطار در چرخه فعلی (۱ تا ۶)
            created_at REAL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS mutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            reason TEXT,
            has_reason INTEGER DEFAULT 1,
            muted_at REAL,
            until_at REAL,        -- NULL یعنی سکوت نامحدود
            active INTEGER DEFAULT 1
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            reason TEXT,
            has_reason INTEGER DEFAULT 1,
            banned_at REAL,
            active INTEGER DEFAULT 1
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS blacklist_gifs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            file_unique_id TEXT,
            added_at REAL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS blacklist_stickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            file_unique_id TEXT,
            added_at REAL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bad_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,   -- NULL یعنی سراسری (برای همه گروه‌ها)
            word TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS warning_texts (
            chat_id INTEGER,     -- NULL یعنی پیش‌فرض سراسری
            level INTEGER,
            text TEXT,
            sticker_file_id TEXT,
            gif_file_id TEXT,
            PRIMARY KEY (chat_id, level)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS group_admins_extra (
            chat_id INTEGER,
            user_id INTEGER,
            granted_by INTEGER,
            can_manage_other_admins INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS group_features (
            chat_id INTEGER,
            feature_key TEXT,
            enabled INTEGER DEFAULT 1,
            PRIMARY KEY (chat_id, feature_key)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            reporter_id INTEGER,
            reporter_username TEXT,
            reported_user_id INTEGER,
            reported_username TEXT,
            message_snippet TEXT,
            created_at REAL,
            sent INTEGER DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS welcome_messages (
            chat_id INTEGER PRIMARY KEY,
            text TEXT,
            sticker_file_id TEXT,
            animation_file_id TEXT
        )
        """)
        # برای دیتابیس‌های قدیمی که قبلاً بدون این دو ستون ساخته شدن
        for col in ("sticker_file_id", "animation_file_id"):
            try:
                c.execute(f"ALTER TABLE welcome_messages ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass

        # مقداردهی اولیه کلمات بد سراسری در صورت خالی بودن
        c.execute("SELECT COUNT(*) as cnt FROM bad_words WHERE chat_id IS NULL")
        if c.fetchone()["cnt"] == 0:
            for w in DEFAULT_BAD_WORDS:
                c.execute("INSERT INTO bad_words (chat_id, word) VALUES (NULL, ?)", (w,))

        # مقداردهی اولیه متن اخطارها
        c.execute("SELECT COUNT(*) as cnt FROM warning_texts WHERE chat_id IS NULL")
        if c.fetchone()["cnt"] == 0:
            for lvl, txt in DEFAULT_WARNING_TEXTS.items():
                c.execute(
                    "INSERT INTO warning_texts (chat_id, level, text) VALUES (NULL, ?, ?)",
                    (lvl, txt)
                )

        # تنظیمات پیش‌فرض ربات (روشن/خاموش سراسری)
        c.execute("SELECT value FROM bot_settings WHERE key = 'global_active'")
        if c.fetchone() is None:
            c.execute("INSERT INTO bot_settings (key, value) VALUES ('global_active', '1')")
        c.execute("SELECT value FROM bot_settings WHERE key = 'shutdown_message'")
        if c.fetchone() is None:
            c.execute(
                "INSERT INTO bot_settings (key, value) VALUES ('shutdown_message', ?)",
                (DEFAULT_SHUTDOWN_MESSAGE,)
            )


# ---------------------------------------------------------------------------
# گروه‌ها
# ---------------------------------------------------------------------------

def upsert_group(chat_id, title, added_by_user_id=None, added_by_username=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id FROM groups WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE groups SET title=? WHERE chat_id=?", (title, chat_id))
        else:
            c.execute(
                "INSERT INTO groups (chat_id, title, added_by_user_id, added_by_username, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (chat_id, title, added_by_user_id, added_by_username)
            )


def get_group(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
        return c.fetchone()


def get_groups_added_by(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM groups WHERE added_by_user_id=?", (user_id,))
        return c.fetchall()


def get_all_groups():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM groups")
        return c.fetchall()


def set_group_lock(chat_id, locked: bool, until_ts=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE groups SET is_locked=?, lock_until=? WHERE chat_id=?",
            (1 if locked else 0, until_ts, chat_id)
        )


def set_group_active(chat_id, active: bool):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE groups SET is_active=? WHERE chat_id=?", (1 if active else 0, chat_id))


# ---------------------------------------------------------------------------
# اخطارها
# ---------------------------------------------------------------------------

def add_warning(chat_id, user_id, username, reason, level):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO warnings (chat_id, user_id, username, reason, level, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, username, reason, level, time.time())
        )


def get_active_warning_count(chat_id, user_id):
    """تعداد اخطارهای چرخه فعلی (بعد از بن، چرخه ریست می‌شود چون رکوردهای قبل حذف نمی‌شوند
    بلکه بر اساس آخرین بن فیلتر می‌کنیم)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT banned_at FROM bans WHERE chat_id=? AND user_id=? ORDER BY banned_at DESC LIMIT 1",
            (chat_id, user_id)
        )
        last_ban = c.fetchone()
        since = last_ban["banned_at"] if last_ban else 0
        c.execute(
            "SELECT COUNT(*) as cnt FROM warnings WHERE chat_id=? AND user_id=? AND created_at > ?",
            (chat_id, user_id, since)
        )
        return c.fetchone()["cnt"]


def get_user_warnings(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM warnings WHERE chat_id=? AND user_id=? ORDER BY created_at DESC",
            (chat_id, user_id)
        )
        return c.fetchall()


def get_all_warned_users(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT user_id, username, COUNT(*) as cnt, MAX(created_at) as last_at "
            "FROM warnings WHERE chat_id=? GROUP BY user_id ORDER BY last_at DESC",
            (chat_id,)
        )
        return c.fetchall()


def get_warning_text(chat_id, level):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM warning_texts WHERE chat_id=? AND level=?", (chat_id, level))
        row = c.fetchone()
        if row:
            return row
        c.execute("SELECT * FROM warning_texts WHERE chat_id IS NULL AND level=?", (level,))
        return c.fetchone()


def set_warning_text(chat_id, level, text=None, sticker_file_id=None, gif_file_id=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT level FROM warning_texts WHERE chat_id=? AND level=?", (chat_id, level))
        exists = c.fetchone()
        if exists:
            fields, values = [], []
            if text is not None:
                fields.append("text=?"); values.append(text)
            if sticker_file_id is not None:
                fields.append("sticker_file_id=?"); values.append(sticker_file_id)
            if gif_file_id is not None:
                fields.append("gif_file_id=?"); values.append(gif_file_id)
            values += [chat_id, level]
            c.execute(f"UPDATE warning_texts SET {', '.join(fields)} WHERE chat_id=? AND level=?", values)
        else:
            c.execute(
                "INSERT INTO warning_texts (chat_id, level, text, sticker_file_id, gif_file_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (chat_id, level, text, sticker_file_id, gif_file_id)
            )


# ---------------------------------------------------------------------------
# سکوت (Mute)
# ---------------------------------------------------------------------------

def add_mute(chat_id, user_id, username, reason, has_reason, until_at):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE mutes SET active=0 WHERE chat_id=? AND user_id=? AND active=1", (chat_id, user_id))
        c.execute(
            "INSERT INTO mutes (chat_id, user_id, username, reason, has_reason, muted_at, until_at, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (chat_id, user_id, username, reason, 1 if has_reason else 0, time.time(), until_at)
        )


def remove_mute(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE mutes SET active=0 WHERE chat_id=? AND user_id=? AND active=1", (chat_id, user_id))


def update_mute_duration(chat_id, user_id, new_until_ts):
    """تغییر زمان پایان سکوت فعلیِ یک کاربر (بدون تغییر دلیل ثبت‌شده)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE mutes SET until_at=? WHERE chat_id=? AND user_id=? AND active=1",
            (new_until_ts, chat_id, user_id)
        )


def get_mute_record(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM mutes WHERE chat_id=? AND user_id=? AND active=1 ORDER BY muted_at DESC LIMIT 1",
            (chat_id, user_id)
        )
        return c.fetchone()


def get_active_mutes(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM mutes WHERE chat_id=? AND active=1 ORDER BY muted_at DESC", (chat_id,))
        return c.fetchall()


def is_muted(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM mutes WHERE chat_id=? AND user_id=? AND active=1 ORDER BY muted_at DESC LIMIT 1",
            (chat_id, user_id)
        )
        return c.fetchone()


# ---------------------------------------------------------------------------
# بن (Ban)
# ---------------------------------------------------------------------------

def add_ban(chat_id, user_id, username, reason, has_reason):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO bans (chat_id, user_id, username, reason, has_reason, banned_at, active) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (chat_id, user_id, username, reason, 1 if has_reason else 0, time.time())
        )


def get_all_banned_users(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM bans WHERE chat_id=? AND active=1 ORDER BY banned_at DESC", (chat_id,))
        return c.fetchall()


def unban_record(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE bans SET active=0 WHERE chat_id=? AND user_id=? AND active=1", (chat_id, user_id))


# ---------------------------------------------------------------------------
# لیست سیاه گیف / استیکر
# ---------------------------------------------------------------------------

def add_blacklist_gif(chat_id, file_unique_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO blacklist_gifs (chat_id, file_unique_id, added_at) VALUES (?, ?, ?)",
            (chat_id, file_unique_id, time.time())
        )


def is_gif_blacklisted(chat_id, file_unique_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM blacklist_gifs WHERE chat_id=? AND file_unique_id=?",
            (chat_id, file_unique_id)
        )
        return c.fetchone() is not None


def add_blacklist_sticker(chat_id, file_unique_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO blacklist_stickers (chat_id, file_unique_id, added_at) VALUES (?, ?, ?)",
            (chat_id, file_unique_id, time.time())
        )


def is_sticker_blacklisted(chat_id, file_unique_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM blacklist_stickers WHERE chat_id=? AND file_unique_id=?",
            (chat_id, file_unique_id)
        )
        return c.fetchone() is not None


# ---------------------------------------------------------------------------
# کلمات بد
# ---------------------------------------------------------------------------

def get_bad_words(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT word FROM bad_words WHERE chat_id IS NULL OR chat_id=?", (chat_id,))
        return [r["word"] for r in c.fetchall()]


def add_bad_word(chat_id, word):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO bad_words (chat_id, word) VALUES (?, ?)", (chat_id, word))


def remove_bad_word(chat_id, word):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM bad_words WHERE word=? AND (chat_id=? OR chat_id IS NULL)", (word, chat_id))


# ---------------------------------------------------------------------------
# تنظیمات کلی ربات (خاموشی سراسری سازنده)
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
        row = c.fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )


def is_global_active():
    return get_setting("global_active", "1") == "1"


def set_global_active(active: bool):
    set_setting("global_active", "1" if active else "0")


def get_shutdown_message():
    return get_setting("shutdown_message", DEFAULT_SHUTDOWN_MESSAGE)


def set_shutdown_message(text):
    set_setting("shutdown_message", text)


# ---------------------------------------------------------------------------
# مدیران اضافه (مدیرانی که مالک گروه اجازه ویژه بهشون داده)
# ---------------------------------------------------------------------------

def grant_admin_extra_permission(chat_id, user_id, granted_by):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO group_admins_extra (chat_id, user_id, granted_by, can_manage_other_admins) "
            "VALUES (?, ?, ?, 1) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET can_manage_other_admins=1, granted_by=excluded.granted_by",
            (chat_id, user_id, granted_by)
        )


def revoke_admin_extra_permission(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE group_admins_extra SET can_manage_other_admins=0 WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        )


def has_admin_extra_permission(chat_id, user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT can_manage_other_admins FROM group_admins_extra WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        )
        row = c.fetchone()
        return bool(row and row["can_manage_other_admins"])


# ---------------------------------------------------------------------------
# روشن/خاموش کردن قابلیت‌های هر گروه (فیلتر فحش، بازی‌ها، بلک‌لیست و ...)
# ---------------------------------------------------------------------------

# لیست قابلیت‌های قابل روشن/خاموش کردن: کلید داخلی -> نام نمایشی فارسی
TOGGLEABLE_FEATURES = {
    "bad_words": "فیلتر فحش",
    "games": "بازی‌ها",
    "blacklist": "حذف گیف/استیکر بلک‌لیست",
    "photos": "ارسال عکس",
    "videos": "ارسال فیلم",
    "documents": "ارسال فایل",
}


def is_feature_enabled(chat_id, feature_key):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT enabled FROM group_features WHERE chat_id=? AND feature_key=?",
            (chat_id, feature_key)
        )
        row = c.fetchone()
        return bool(row["enabled"]) if row else True  # پیش‌فرض: روشن


def set_feature_enabled(chat_id, feature_key, enabled: bool):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO group_features (chat_id, feature_key, enabled) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, feature_key) DO UPDATE SET enabled=excluded.enabled",
            (chat_id, feature_key, 1 if enabled else 0)
        )


# ---------------------------------------------------------------------------
# گزارش کاربران توسط اعضای عادی (هر ۲ دقیقه یک‌جا برای مالک گروه ارسال می‌شود)
# ---------------------------------------------------------------------------

def add_report(chat_id, reporter_id, reporter_username, reported_user_id, reported_username, message_snippet):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO reports (chat_id, reporter_id, reporter_username, reported_user_id, "
            "reported_username, message_snippet, created_at, sent) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (chat_id, reporter_id, reporter_username, reported_user_id, reported_username,
             message_snippet, time.time())
        )


def get_chats_with_pending_reports():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT chat_id FROM reports WHERE sent=0")
        return [r["chat_id"] for r in c.fetchall()]


def get_pending_reports(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM reports WHERE chat_id=? AND sent=0 ORDER BY created_at", (chat_id,))
        return c.fetchall()


def mark_reports_sent(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE reports SET sent=1 WHERE chat_id=? AND sent=0", (chat_id,))


# ---------------------------------------------------------------------------
# خوش‌آمدگویی به عضو جدید
# ---------------------------------------------------------------------------

DEFAULT_WELCOME_TEXT = "🌼 {user} عزیز، به گروه {group} خوش اومدی!\nامیدواریم لحظات خوبی رو اینجا بگذرونی."


def get_welcome_text(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT text FROM welcome_messages WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        return row["text"] if row else DEFAULT_WELCOME_TEXT


def set_welcome_text(chat_id, text):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO welcome_messages (chat_id, text) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET text=excluded.text",
            (chat_id, text)
        )


def reset_welcome_text(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM welcome_messages WHERE chat_id=?", (chat_id,))


def set_welcome_media(chat_id, sticker_file_id=None, animation_file_id=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id FROM welcome_messages WHERE chat_id=?", (chat_id,))
        exists = c.fetchone()
        if exists:
            if sticker_file_id is not None:
                c.execute(
                    "UPDATE welcome_messages SET sticker_file_id=?, animation_file_id=NULL WHERE chat_id=?",
                    (sticker_file_id, chat_id)
                )
            else:
                c.execute(
                    "UPDATE welcome_messages SET animation_file_id=?, sticker_file_id=NULL WHERE chat_id=?",
                    (animation_file_id, chat_id)
                )
        else:
            c.execute(
                "INSERT INTO welcome_messages (chat_id, text, sticker_file_id, animation_file_id) "
                "VALUES (?, ?, ?, ?)",
                (chat_id, DEFAULT_WELCOME_TEXT, sticker_file_id, animation_file_id)
            )


def get_welcome_media(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT sticker_file_id, animation_file_id FROM welcome_messages WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        if not row:
            return None, None
        return row["sticker_file_id"], row["animation_file_id"]


def clear_welcome_media(chat_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE welcome_messages SET sticker_file_id=NULL, animation_file_id=NULL WHERE chat_id=?",
            (chat_id,)
        )
