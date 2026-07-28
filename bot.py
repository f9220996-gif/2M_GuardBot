import requests
import time
from datetime import datetime, timedelta
import pytz

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"

# ====== لیست کلمات بد (بدون کسخل و بی‌شرف) ======
bad_words = [
    "فحش", "کیر", "کص", "کس", "کون", "خایه", "جنده",
    "حرومزاده", "پدرسگ", "مادرجنده", "ناموس",
    "کونی", "کسکش", "پدرتو",
    "مادرتو", "خواهرتو", "ممه"
]

bad_gifs = []
bad_stickers = []
muted_users = {}
group_locked = False
last_update = 0

# ====== منطقه زمانی ایران ======
IRAN_TZ = pytz.timezone('Asia/Tehran')

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

def is_admin(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    r = requests.post(url, data=data).json()
    if r.get("ok"):
        status = r.get("result", {}).get("status")
        return status in ["creator", "administrator"]
    return False

def format_time(dt):
    """تبدیل زمان به ساعت و دقیقه به فرمت ایران"""
    iran_time = dt.astimezone(IRAN_TZ)
    return iran_time.strftime("%H:%M")

print("✅ ربات M2_GuardBot با نمایش ساعت خفه شدن روشن شد!")

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
            
            # ====== دستور /start ======
            if text == "/start":
                send_message(chat_id, "✅ ربات پاک‌کننده فعال است!\n\n"
                                      "دستورات مدیران:\n"
                                      "خاموشی - قفل گروه\n"
                                      "روشن - باز کردن گروه\n"
                                      "خفه 5 (ریپلای) - خفه کردن کاربر به دقیقه دلخواه\n"
                                      "آزاد کن (ریپلای) - برداشتن خفه‌گی\n"
                                      "بن کن (ریپلای) - بن کاربر\n"
                                      "گیف بد (ریپلای روی گیف) - اضافه کردن گیف بد\n"
                                      "استیکر بد (ریپلای روی استیکر) - اضافه کردن استیکر بد")
                continue
            
            # ====== دستورات فقط برای مدیرها ======
            if is_user_admin:
                
                # خاموشی/روشن
                if text == "خاموشی":
                    group_locked = True
                    send_message(chat_id, "🔒 گروه خاموش شد!")
                    continue
                if text == "روشن":
                    group_locked = False
                    send_message(chat_id, "🔓 گروه روشن شد!")
                    continue
                
                # ====== خفه کردن با ریپلای (دستور "خفه") ======
                if text.startswith("خفه") and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    try:
                        minutes = int(text.replace("خفه", "").strip())
                        if minutes > 0:
                            mute_user(chat_id, target, minutes)
                            until_time = format_time(muted_users[target])
                            send_message(chat_id, f"🔇 کاربر {target_name} رو {minutes} دقیقه خفه کرد! (تا ساعت {until_time})")
                        else:
                            send_message(chat_id, "❗ عدد باید بزرگتر از ۰ باشه!")
                    except:
                        send_message(chat_id, "❗ دستور: خفه 5 (عدد به دقیقه)")
                    continue
                
                # ====== آزاد کن (برداشتن خفه‌گی) ======
                if text == "آزاد کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    unmute_user(chat_id, target)
                    send_message(chat_id, f"🔊 خفه‌گی {target_name} برداشته شد!")
                    continue
                
                # ====== بن کن ======
                if text == "بن کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    target_name = get_user_name(chat_id, target)
                    url = f"https://api.telegram.org/bot{TOKEN}/banChatMember"
                    data = {"chat_id": chat_id, "user_id": target}
                    requests.post(url, data=data)
                    send_message(chat_id, f"🚫 کاربر {target_name} بن شد!")
                    continue
                
                # ====== اضافه کردن گیف بد ======
                if text == "گیف بد" and msg.get("reply_to_message"):
                    gif = msg["reply_to_message"].get("animation")
                    if gif:
                        bad_gifs.append(gif["file_id"])
                        send_message(chat_id, "✅ گیف به لیست سیاه اضافه شد!")
                    continue
                
                # ====== اضافه کردن استیکر بد ======
                if text == "استیکر بد" and msg.get("reply_to_message"):
                    sticker = msg["reply_to_message"].get("sticker")
                    if sticker:
                        bad_stickers.append(sticker["file_id"])
                        send_message(chat_id, "✅ استیکر به لیست سیاه اضافه شد!")
                    continue
            
            # ====== چک قفل گروه ======
            if group_locked and not is_user_admin:
                delete_message(chat_id, message_id)
                continue
            
            # ====== چک خفه‌گی (تایم‌اوت) ======
            if user_id in muted_users and not is_user_admin:
                if datetime.now() < muted_users[user_id]:
                    delete_message(chat_id, message_id)
                    continue
                else:
                    del muted_users[user_id]
            
            # ====== اگر کاربر مدیر هست، هیچ فیلتری روش اعمال نشه ======
            if is_user_admin:
                continue  # مدیرها از همه چیز معاف‌اند
            
            # ====== چک کلمات بد (خودکار ۱ دقیقه خفه) ======
            if text:
                for word in bad_words:
                    if word in text:
                        delete_message(chat_id, message_id)
                        mute_user(chat_id, user_id, 1)
                        user_name = get_user_name(chat_id, user_id)
                        until_time = format_time(muted_users[user_id])
                        send_message(chat_id, f"🚫 پیام {user_name} حاوی '{word}' پاک شد! تا ساعت {until_time} خفه شدی.")
                        break
            
            # ====== چک گیف‌های بد (خودکار ۳ دقیقه خفه) ======
            if "animation" in msg:
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    delete_message(chat_id, message_id)
                    mute_user(chat_id, user_id, 3)
                    user_name = get_user_name(chat_id, user_id)
                    until_time = format_time(muted_users[user_id])
                    send_message(chat_id, f"🚫 گیف بد {user_name} پاک شد! تا ساعت {until_time} خفه شدی.")
            
            # ====== چک استیکرهای بد (خودکار ۳ دقیقه خفه) ======
            if "sticker" in msg:
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    delete_message(chat_id, message_id)
                    mute_user(chat_id, user_id, 3)
                    user_name = get_user_name(chat_id, user_id)
                    until_time = format_time(muted_users[user_id])
                    send_message(chat_id, f"🚫 استیکر بد {user_name} پاک شد! تا ساعت {until_time} خفه شدی.")
        
        time.sleep(1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(2)