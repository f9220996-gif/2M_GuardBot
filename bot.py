import requests
import time
from datetime import datetime, timedelta

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"

# ====== آیدی عددی خودت (صاحب ربات) ======
OWNER_ID = 7353819350  # این تو هستی، حتی اگه مالک گروه نباشی

# ====== کلماتی که چک میکنه (مهدی/FFX) ======
check_words = ["مهدی", "FFX", "اف اف یکس", "اف اف مکس"]

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

# ====== سیستم اخطار ======
user_warnings = {}  # {'user_id': count}

def send_message(chat_id, text, reply_to=None, delete_after=60):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    r = requests.post(url, data=data).json()
    
    if r.get("ok") and delete_after > 0:
        message_id = r.get("result", {}).get("message_id")
        time.sleep(delete_after)
        delete_message(chat_id, message_id)
    return r

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
    
    # ====== اگر کاربر OWNER_ID باشه، هر کاری می‌تونه بکنه ======
    if moderator_id == OWNER_ID:
        return True, ""
    
    # ====== مدیرهای معمولی ======
    if moderator_status == "administrator":
        if target_status in ["creator", "administrator"]:
            return False, "❌ نمی‌تونی یک مدیر رو بن یا خفه کنی!"
        return True, ""
    
    if moderator_status == "creator":
        return True, ""
    
    return False, "❌ شما دسترسی لازم رو ندارید!"

def format_datetime(dt):
    return dt.strftime("%Y/%m/%d - %H:%M")

def is_user_online(user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChat"
    data = {"chat_id": user_id}
    try:
        r = requests.post(url, data=data).json()
        return r.get("ok", False)
    except:
        return False

print("✅ ربات M2_GuardBot با دسترسی کامل برای OWNER روشن شد!")

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
            
            # ====== چک کردن کلمات مهدی/FFX (برای همه کاربران) ======
            if text:
                for word in check_words:
                    if word in text:
                        if user_id == OWNER_ID:
                            break
                        
                        if is_user_online(OWNER_ID):
                            pass
                        else:
                            send_message(chat_id, "عشقم ان نیس 😔", reply_to=message_id, delete_after=30)
                        break
            
            # ====== ادامه کد قبلی ======
            
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
                                      "⚠️ OWNER (سازنده ربات) می‌تونه همه رو بن/خفه کنه.\n"
                                      "⏱️ سیستم اخطار: ۳ بار اخطار، بعد خفه ۵ دقیقه",
                             reply_to=message_id, delete_after=60)
                continue
            
            if is_user_admin:
                
                if text == "خاموشی":
                    group_locked = True
                    send_message(chat_id, "🔒 گروه خاموش شد!", reply_to=message_id, delete_after=60)
                    continue
                if text == "روشن":
                    group_locked = False
                    send_message(chat_id, "🔓 گروه روشن شد!", reply_to=message_id, delete_after=60)
                    continue
                
                if text == "گیف بد" and msg.get("reply_to_message"):
                    gif = msg["reply_to_message"].get("animation")
                    if gif:
                        bad_gifs.append(gif["file_id"])
                        send_message(chat_id, "✅ گیف به لیست سیاه اضافه شد!", reply_to=message_id, delete_after=60)
                    continue
                
                if text == "استیکر بد" and msg.get("reply_to_message"):
                    sticker = msg["reply_to_message"].get("sticker")
                    if sticker:
                        bad_stickers.append(sticker["file_id"])
                        send_message(chat_id, "✅ استیکر به لیست سیاه اضافه شد!", reply_to=message_id, delete_after=60)
                    continue
                
                if text.startswith("خفه") and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg, reply_to=message_id, delete_after=60)
                        continue
                    
                    try:
                        minutes = int(text.replace("خفه", "").strip())
                        if minutes > 0:
                            mute_user(chat_id, target, minutes)
                            until_datetime = format_datetime(muted_users[target])
                            send_message(chat_id, f"🔇 کاربر {target_name} رو {minutes} دقیقه خفه کرد! (تا {until_datetime})", reply_to=message_id, delete_after=60)
                        else:
                            send_message(chat_id, "❗ عدد باید بزرگتر از ۰ باشه!", reply_to=message_id, delete_after=60)
                    except:
                        send_message(chat_id, "❗ دستور: خفه 5 (عدد به دقیقه)", reply_to=message_id, delete_after=60)
                    continue
                
                if text == "آزاد کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg, reply_to=message_id, delete_after=60)
                        continue
                    
                    unmute_user(chat_id, target)
                    send_message(chat_id, f"🔊 خفه‌گی {target_name} برداشته شد!", reply_to=message_id, delete_after=60)
                    continue
                
                if text == "بن کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    
                    can_moderate, error_msg = can_target_be_moderated(chat_id, user_id, target)
                    if not can_moderate:
                        send_message(chat_id, error_msg, reply_to=message_id, delete_after=60)
                        continue
                    
                    url = f"https://api.telegram.org/bot{TOKEN}/banChatMember"
                    data = {"chat_id": chat_id, "user_id": target}
                    requests.post(url, data=data)
                    send_message(chat_id, f"🚫 کاربر {target_name} بن شد!", reply_to=message_id, delete_after=60)
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
            
            # ====== سیستم اخطار برای کلمات بد ======
            if text:
                for word in bad_words:
                    if word in text:
                        delete_message(chat_id, message_id)
                        
                        user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                        warn_count = user_warnings[user_id]
                        
                        if warn_count == 1:
                            send_message(chat_id, f"⚠️ اخطار اول! لطفاً از کلمات نامناسب استفاده نکنید. (دفعه بعد اخطار دوم)", reply_to=message_id, delete_after=60)
                        elif warn_count == 2:
                            send_message(chat_id, f"⚠️⚠️ اخطار دوم! اگر ادامه بدی، اخطار سوم رو میگیری.", reply_to=message_id, delete_after=60)
                        elif warn_count == 3:
                            send_message(chat_id, f"⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
                        elif warn_count >= 4:
                            mute_user(chat_id, user_id, 5)
                            user_name = get_user_name(chat_id, user_id)
                            until_datetime = format_datetime(muted_users[user_id])
                            send_message(chat_id, f"🚫 {user_name} بعد از ۳ بار اخطار، ۵ دقیقه خفه شد! (تا {until_datetime})", reply_to=message_id, delete_after=60)
                            user_warnings[user_id] = 0
                        break
            
            if "animation" in msg:
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    delete_message(chat_id, message_id)
                    
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    warn_count = user_warnings[user_id]
                    
                    if warn_count == 1:
                        send_message(chat_id, f"⚠️ اخطار اول! گیف نامناسب نفرستید.", reply_to=message_id, delete_after=60)
                    elif warn_count == 2:
                        send_message(chat_id, f"⚠️⚠️ اخطار دوم!", reply_to=message_id, delete_after=60)
                    elif warn_count == 3:
                        send_message(chat_id, f"⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
                    elif warn_count >= 4:
                        mute_user(chat_id, user_id, 5)
                        user_name = get_user_name(chat_id, user_id)
                        until_datetime = format_datetime(muted_users[user_id])
                        send_message(chat_id, f"🚫 {user_name} بعد از ۳ بار اخطار، ۵ دقیقه خفه شد! (تا {until_datetime})", reply_to=message_id, delete_after=60)
                        user_warnings[user_id] = 0
            
            if "sticker" in msg:
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    delete_message(chat_id, message_id)
                    
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    warn_count = user_warnings[user_id]
                    
                    if warn_count == 1:
                        send_message(chat_id, f"⚠️ اخطار اول! استیکر نامناسب نفرستید.", reply_to=message_id, delete_after=60)
                    elif warn_count == 2:
                        send_message(chat_id, f"⚠️⚠️ اخطار دوم!", reply_to=message_id, delete_after=60)
                    elif warn_count == 3:
                        send_message(chat_id, f"⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
                    elif warn_count >= 4:
                        mute_user(chat_id, user_id, 5)
                        user_name = get_user_name(chat_id, user_id)
                        until_datetime = format_datetime(muted_users[user_id])
                        send_message(chat_id, f"🚫 {user_name} بعد از ۳ بار اخطار، ۵ دقیقه خفه شد! (تا {until_datetime})", reply_to=message_id, delete_after=60)
                        user_warnings[user_id] = 0
        
        time.sleep(1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(2)