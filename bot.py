import requests
import time
from datetime import datetime, timedelta

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"

# ====== لیست کلمات بد ======
bad_words = [
    "جنده", "حرومزاده", "پدرسگ", "مادرجنده", "ناموس",
    "کونی", "کسکش", "پدرتو", "مادرتو", "خواهرتو", "ممه",
    "مادر", "پدر", "خواهر"
]

bad_gifs = []
bad_stickers = []
muted_users = {}
group_locked = False
last_update = 0

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
    data = {"chat_id": chat_id, "message_id": message_id}
    requests.post(url, data=data)

def mute_user(chat_id, user_id, minutes):
    until_date = datetime.now() + timedelta(minutes=minutes)
    muted_users[user_id] = until_date
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {
        "chat_id": chat_id,
        "user_id": user_id,
        "permissions": {"can_send_messages": False},
        "until_date": int(until_date.timestamp())
    }
    requests.post(url, data=data)

def unmute_user(chat_id, user_id):
    if user_id in muted_users:
        del muted_users[user_id]
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {
        "chat_id": chat_id,
        "user_id": user_id,
        "permissions": {"can_send_messages": True}
    }
    requests.post(url, data=data)

def get_user_name(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    r = requests.post(url, data=data).json()
    if r.get("ok"):
        user = r.get("result", {}).get("user", {})
        name = user.get("first_name", "")
        if user.get("last_name"):
            name += " " + user.get("last_name")
        if user.get("username"):
            name += f" (@{user.get('username')})"
        return name or str(user_id)
    return str(user_id)

def get_user_status(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    r = requests.post(url, data=data).json()
    if r.get("ok"):
        return r.get("result", {}).get("status")
    return "member"

def is_admin(chat_id, user_id):
    status = get_user_status(chat_id, user_id)
    return status in ["creator", "administrator"]

def can_target_be_moderated(chat_id, moderator_id, target_id):
    moderator_status = get_user_status(chat_id, moderator_id)
    target_status = get_user_status(chat_id, target_id)
    
    if moderator_id == target_id:
        return False, "❌ نمی‌تونی خودت رو بن یا خفه کنی!"
    
    if moderator_status == "administrator":
        if target_status in ["creator", "administrator"]:
            return False, "❌ نمی‌تونی یک مدیر رو بن یا خفه کنی!"
        return True, ""
    
    if moderator_status == "creator":
        return True, ""
    
    return False, "❌ شما دسترسی لازم رو ندارید!"

def format_datetime(dt):
    return dt.strftime("%Y/%m/%d - %H:%M")

print("✅ ربات M2_GuardBot نسخه نهایی روشن شد!")

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update+1}"
        r = requests.get(url).json()
        
        for update in r.get("result", []):
            last_update = update["update_id"]
            msg = update.get("message")
            if not msg:
                continue
            
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")
            message_id = msg["message_id"]
            is_user_admin = is_admin(chat_id, user_id)
            
            if text == "/start":
                send_message(chat_id, "✅ ربات پاک‌کننده فعال است!\n\n"
                                      "دستورات:\n"
                                      "خاموشی - قفل گروه (مدیرها)\n"
                                      "روشن - باز کردن گروه (مدیرها)\n"
                                      "خفه 5 (ریپلای) - خفه کردن کاربر\n"
                                      "آزاد کن (ریپلای) - برداشتن خفه‌گی\n"
                                      "بن کن (ریپلای) - بن کاربر\n"
                                      "گیف بد (ریپلای روی گیف) - اضافه کردن گیف بد (مدیرها)\n"
                                      "استیکر بد (ریپلای روی استیکر) - اضافه کردن استیکر بد (مدیرها)\n\n"
                                      "⚠️ فقط سازنده گروه می‌تونه مدیرها رو بن یا خفه کنه.")
                continue
            
            if is_user_admin:
                
                if text == "خاموشی":
                    group_locked = True
                    send_message(chat_id, "🔒 گروه خاموش شد!")
                    continue
                if text == "روشن":
                    group_locked = False
                    send_message(chat_id, "🔓 گروه روشن شد!")
                    continue
                
                if text == "گیف بد" and msg.get("reply_to_message"):
                    gif = msg["reply_to_message"].get("animation")
                    if gif:
                        bad_gifs.append(gif["file_id"])
                        send_message(chat_id, "✅ گیف به لیست سیاه اضافه شد!")
                    continue
                
                if text == "استیکر بد" and msg.get("reply_to_message"):
                    sticker = msg["reply_to_message"].get("sticker")
                    if sticker:
                        bad_stickers.append(sticker["file_id"])
                        send_message(chat_id, "✅ استیکر به لیست سیاه اضافه شد!")
                    continue
                
                if text.startswith("خفه") and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg)
                        continue
                    
                    try:
                        minutes = int(text.replace("خفه", "").strip())
                        if minutes > 0:
                            mute_user(chat_id, target, minutes)
                            until_datetime = format_datetime(muted_users[target])
                            send_message(chat_id, f"🔇 کاربر {target_name} رو {minutes} دقیقه خفه کرد! (تا {until_datetime})")
                        else:
                            send_message(chat_id, "❗ عدد باید بزرگتر از ۰ باشه!")
                    except:
                        send_message(chat_id, "❗ دستور: خفه 5 (عدد به دقیقه)")
                    continue
                
                if text == "آزاد کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg)
                        continue
                    
                    unmute_user(chat_id, target)
                    send_message(chat_id, f"🔊 خفه‌گی {target_name} برداشته شد!")
                    continue
                
                if text == "بن کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg)
                        continue
                    
                    url = f"https://api.telegram.org/bot{TOKEN}/banChatMember"
                    data = {"chat_id": chat_id, "user_id": target}
                    requests.post(url, data=data)
                    send_message(chat_id, f"🚫 کاربر {target_name} بن شد!")
                    continue
            
            if group_locked and not is_user_admin:
                delete_message(chat_id, message_id)
                continue
            
            if user_id in muted_users and not is_user_admin:
                if datetime.now() < muted_users[user_id]:
                    delete_message(chat_id, message_id)
                    continue
                else:
                    del muted_users[user_id]
            
            if is_user_admin:
                continue
            
            if text:
                for word in bad_words:
                    if word in text:
                        delete_message(chat_id, message_id)
                        mute_user(chat_id, user_id, 1)
                        user_name = get_user_name(chat_id, user_id)
                        until_datetime = format_datetime(muted_users[user_id])
                        send_message(chat_id, f"🚫 پیام {user_name} حاوی '{word}' پاک شد! تا {until_datetime} خفه شدی.")
                        break
            
            if "animation" in msg:
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    delete_message(chat_id, message_id)
                    mute_user(chat_id, user_id, 3)
                    user_name = get_user_name(chat_id, user_id)
                    until_datetime = format_datetime(muted_users[user_id])
                    send_message(chat_id, f"🚫 گیف بد {user_name} پاک شد! تا {until_datetime} خفه شدی.")
            
            if "sticker" in msg:
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    delete_message(chat_id, message_id)
                    mute_user(chat_id, user_id, 3)
                    user_name = get_user_name(chat_id, user_id)
                    until_datetime = format_datetime(muted_users[user_id])
                    send_message(chat_id, f"🚫 استیکر بد {user_name} پاک شد! تا {until_datetime} خفه شدی.")
        
        time.sleep(1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(2)