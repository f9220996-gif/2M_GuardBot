import requests
import time
from datetime import datetime, timedelta
import pytz

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"

# ====== آیدی عددی خودت (صاحب ربات) ======
OWNER_ID = 7353819350

# ====== منطقه زمانی ایران ======
IRAN_TZ = pytz.timezone('Asia/Tehran')

# ====== کلماتی که چک میکنه (مهدی/FFX) ======
check_words = ["مهدی", "FFX", "اف اف یکس", "اف اف مکس"]

# ====== کلمات مخصوص OWNER (فقط خودت) ======
owner_phrases = {
    "سلام": "سلام عشقم خوبی؟ 😘",
    "اکس": "سلام عشقم خوبی؟ 😘",
    "خوب عشقم تو چطوری": "خوبم عشقم چیکار میکنی؟ ❤️",
    "خوبی": "خوبم عشقم، تو خوبی؟ 😍",
    "عشقم": "جانم عشقم ❤️",
}

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
user_warnings = {}
sent_messages = set()
joined_users = set()

def send_message(chat_id, text, reply_to=None, delete_after=60):
    msg_key = f"{chat_id}_{text[:20]}"
    if msg_key in sent_messages:
        return None
    sent_messages.add(msg_key)
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, data=data).json()
        if r.get("ok") and delete_after > 0:
            message_id = r.get("result", {}).get("message_id")
            time.sleep(delete_after)
            delete_message(chat_id, message_id)
        return r
    except:
        return None

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
    data = {"chat_id": chat_id, "message_id": message_id}
    try:
        requests.post(url, data=data)
    except:
        pass

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
    try:
        requests.post(url, data=data)
    except:
        pass

def unmute_user(chat_id, user_id):
    if user_id in muted_users:
        del muted_users[user_id]
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {
        "chat_id": chat_id,
        "user_id": user_id,
        "permissions": {"can_send_messages": True}
    }
    try:
        requests.post(url, data=data)
    except:
        pass

def get_user_name(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    try:
        r = requests.post(url, data=data).json()
        if r.get("ok"):
            user = r.get("result", {}).get("user", {})
            name = user.get("first_name", "")
            if user.get("last_name"):
                name += " " + user.get("last_name")
            if user.get("username"):
                name += f" (@{user.get('username')})"
            return name or str(user_id)
    except:
        pass
    return str(user_id)

def get_user_status(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    try:
        r = requests.post(url, data=data).json()
        if r.get("ok"):
            return r.get("result", {}).get("status")
    except:
        pass
    return "member"

def is_admin(chat_id, user_id):
    status = get_user_status(chat_id, user_id)
    return status in ["creator", "administrator"]

def can_target_be_moderated(chat_id, moderator_id, target_id):
    moderator_status = get_user_status(chat_id, moderator_id)
    target_status = get_user_status(chat_id, target_id)
    
    if moderator_id == target_id:
        return False, "❌ نمی‌تونی خودت رو بن یا خفه کنی!"
    
    if moderator_id == OWNER_ID:
        return True, ""
    
    if moderator_status == "administrator":
        if target_status in ["creator", "administrator"]:
            return False, "❌ نمی‌تونی یک مدیر رو بن یا خفه کنی!"
        return True, ""
    
    if moderator_status == "creator":
        return True, ""
    
    return False, "❌ شما دسترسی لازم رو ندارید!"

def format_datetime(dt):
    iran_time = dt.astimezone(IRAN_TZ)
    return iran_time.strftime("%Y/%m/%d - %H:%M")

def get_persian_date():
    """گرفتن تاریخ امروز ایران"""
    now = datetime.now(IRAN_TZ)
    try:
        import jdatetime
        persian_date = jdatetime.datetime.fromgregorian(datetime=now)
        return f"{persian_date.year}/{persian_date.month}/{persian_date.day} - {persian_date.hour}:{persian_date.minute}"
    except:
        return now.strftime("%Y/%m/%d - %H:%M")

def welcome_message(user_name):
    welcomes = [
        f"🌟 به جمع ما خوش آمدی، {user_name}! 🌟\nامیدواریم لحظات خوشی رو اینجا داشته باشی! 🎉",
        f"👑 سلام {user_name} عزیز! 👑\nورودت رو به این خانواده بزرگ تبریک می‌گم! ❤️",
        f"🎊 {user_name} جان! 🎊\nقدم روي چشم! اینجا جای تو خالی بود! 😍",
        f"💫 {user_name} عزیز! 💫\nبه جمع گرم ما خوش اومدی! امیدواریم باحال باشی! 🔥",
        f"🌺 سلام {user_name}! 🌺\nورودت رو تبریک می‌گم! اینجا خونه‌ی خودته! 🏠",
        f"✨ {user_name} عزیز! ✨\nاز اینکه به جمع ما پیوستی خوشحالم! ❤️",
        f"🥳 {user_name} جان! 🥳\nبه خانواده‌ی ۲M IRAN خوش اومدی! 🎉"
    ]
    return welcomes[hash(user_name) % len(welcomes)]

print("✅ ربات M2_GuardBot با محدودیت پیوی فقط برای OWNER روشن شد!")

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update+1}"
        r = requests.get(url).json()
        
        for update in r.get("result", []):
            last_update = update["update_id"]
            
            # ====== چک کردن عضو جدید ======
            if "message" in update and "new_chat_members" in update["message"]:
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                # فقط توی گروه خوش‌آمدگویی بگه
                if msg["chat"]["type"] != "private":
                    for new_member in msg["new_chat_members"]:
                        user_id = new_member.get("id")
                        if user_id and user_id != OWNER_ID and user_id not in joined_users:
                            joined_users.add(user_id)
                            user_name = new_member.get("first_name", "کاربر")
                            welcome_text = welcome_message(user_name)
                            send_message(chat_id, welcome_text, reply_to=msg["message_id"], delete_after=300)
            
            msg = update.get("message")
            if not msg:
                continue
            
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            chat_type = msg["chat"]["type"]  # private, group, supergroup
            text = msg.get("text", "")
            message_id = msg["message_id"]
            is_user_admin = is_admin(chat_id, user_id)
            
            # ====== اگر پیوی (private) هست ======
            if chat_type == "private":
                # فقط OWNER می‌تونه توی پیوی جواب بگیره
                if user_id == OWNER_ID:
                    # OWNER می‌تونه /start بزنه یا پیام بفرسته
                    if text == "/start":
                        send_message(chat_id, "✅ ربات فعال است!\n\nدستورات گروه:\nخاموشی/روشن\nخفه/آزاد کن/بن کن\nگیف بد/استیکر بد")
                        continue
                    # پاسخ به OWNER
                    if text in owner_phrases:
                        send_message(chat_id, owner_phrases[text], reply_to=message_id, delete_after=30)
                        continue
                    elif text == "تاریخ":
                        send_message(chat_id, f"📅 تاریخ امروز ایران:\n{get_persian_date()}", reply_to=message_id, delete_after=30)
                        continue
                else:
                    # بقیه کاربران توی پیوی جواب نمی‌گیرند (نادیده گرفته می‌شوند)
                    continue
            
            # ====== بقیه کد فقط برای گروه ======
            
            # ====== چک کردن کلمات مهدی/FFX ======
            if text:
                for word in check_words:
                    if word in text:
                        if user_id == OWNER_ID:
                            break
                        
                        if is_user_online(OWNER_ID):
                            pass
                        else:
                            send_message(chat_id, "آقامون نیستن 😔", reply_to=message_id, delete_after=30)
                        break
            
            # ====== دستورات مدیریتی ======
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
                
                if text == "تاریخ":
                    send_message(chat_id, f"📅 تاریخ امروز ایران:\n{get_persian_date()}", reply_to=message_id, delete_after=60)
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
                            send_message(chat_id, "⚠️ اخطار اول! لطفاً از کلمات نامناسب استفاده نکنید.", reply_to=message_id, delete_after=60)
                        elif warn_count == 2:
                            send_message(chat_id, "⚠️⚠️ اخطار دوم! اگر ادامه بدی، اخطار سوم رو میگیری.", reply_to=message_id, delete_after=60)
                        elif warn_count == 3:
                            send_message(chat_id, "⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
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
                        send_message(chat_id, "⚠️ اخطار اول! گیف نامناسب نفرستید.", reply_to=message_id, delete_after=60)
                    elif warn_count == 2:
                        send_message(chat_id, "⚠️⚠️ اخطار دوم!", reply_to=message_id, delete_after=60)
                    elif warn_count == 3:
                        send_message(chat_id, "⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
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
                        send_message(chat_id, "⚠️ اخطار اول! استیکر نامناسب نفرستید.", reply_to=message_id, delete_after=60)
                    elif warn_count == 2:
                        send_message(chat_id, "⚠️⚠️ اخطار دوم!", reply_to=message_id, delete_after=60)
                    elif warn_count == 3:
                        send_message(chat_id, "⚠️⚠️⚠️ اخطار سوم! دفعه بعد ۵ دقیقه خفه میشی!", reply_to=message_id, delete_after=60)
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