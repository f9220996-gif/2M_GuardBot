import requests
import time
from datetime import datetime, timedelta
import pytz
import threading

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"
OWNER_ID = 7353819350
IRAN_TZ = pytz.timezone('Asia/Tehran')

check_words = ["مهدی", "FFX", "اف اف یکس", "اف اف مکس"]
owner_phrases = {"سلام": "سلام عشقم خوبی؟ 😘", "اکس": "سلام عشقم خوبی؟ 😘"}
bad_words = ["جنده", "حرومزاده", "پدرسگ", "مادرجنده", "ناموس", "کونی", "کسکش", "پدرتو", "مادرتو", "خواهرتو", "ممه", "مادر", "پدر", "خواهر", "کیر"]

bad_gifs, bad_stickers, muted_users, user_warnings = [], [], {}, {}
group_locked, last_update = False, 0
processed = set()
sent_cache = {}  # کش برای تشخیص پیام‌های تکراری

def send_msg(chat_id, text, reply_to=None, delete_after=60):
    # ====== تشخیص پیام تکراری ======
    key = f"{chat_id}_{text[:50]}"
    now = time.time()
    if key in sent_cache and now - sent_cache[key] < 5:
        # پیام تکراریه، پاکش کن
        return None
    sent_cache[key] = now
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, data=data, timeout=5).json()
        if r.get("ok") and delete_after > 0:
            mid = r["result"]["message_id"]
            threading.Thread(target=delayed_delete, args=(chat_id, mid, delete_after), daemon=True).start()
        return r
    except:
        return None

def delayed_delete(chat_id, msg_id, delay):
    time.sleep(delay)
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id}, timeout=3)
    except:
        pass

def del_msg(chat_id, msg_id):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id}, timeout=3)
    except:
        pass

def mute(chat_id, user_id, minutes):
    until = datetime.now() + timedelta(minutes=minutes)
    muted_users[user_id] = until
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {"chat_id": chat_id, "user_id": user_id, "permissions": {"can_send_messages": False}, "until_date": int(until.timestamp())}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def unmute(chat_id, user_id):
    if user_id in muted_users:
        del muted_users[user_id]
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {"chat_id": chat_id, "user_id": user_id, "permissions": {"can_send_messages": True}}
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

def get_name(chat_id, user_id):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getChatMember", data={"chat_id": chat_id, "user_id": user_id}, timeout=5).json()
        if r.get("ok"):
            u = r["result"]["user"]
            name = u.get("first_name", "")
            if u.get("last_name"):
                name += " " + u.get("last_name")
            if u.get("username"):
                name += f" (@{u.get('username')})"
            return name or str(user_id)
    except:
        pass
    return str(user_id)

def get_status(chat_id, user_id):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getChatMember", data={"chat_id": chat_id, "user_id": user_id}, timeout=5).json()
        return r.get("result", {}).get("status", "member")
    except:
        return "member"

def is_admin(chat_id, user_id):
    status = get_status(chat_id, user_id)
    return status in ["creator", "administrator"]

def is_group_owner(chat_id, user_id):
    status = get_status(chat_id, user_id)
    return status == "creator"

def can_moderate(chat_id, moderator_id, target_id):
    if moderator_id == OWNER_ID:
        return True, ""
    if not is_admin(chat_id, moderator_id) and not is_group_owner(chat_id, moderator_id):
        return False, "❌ شما دسترسی لازم رو ندارید!"
    if moderator_id == target_id:
        return False, "❌ نمی‌تونی خودت رو سکوت کنی!"
    if is_group_owner(chat_id, moderator_id):
        return True, ""
    if get_status(chat_id, target_id) in ["creator", "administrator"]:
        return False, "❌ نمی‌تونی یک مدیر رو سکوت کنی!"
    return True, ""

def format_time(dt):
    return dt.astimezone(IRAN_TZ).strftime("%Y/%m/%d - %H:%M")

def get_date():
    now = datetime.now(IRAN_TZ)
    try:
        import jdatetime
        d = jdatetime.datetime.fromgregorian(datetime=now)
        return f"{d.year}/{d.month}/{d.day} - {d.hour}:{d.minute}"
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

print("✅ ربات M2_GuardBot با قابلیت پاک کردن پیام تکراری روشن شد!")

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update+1}"
        r = requests.get(url, timeout=10).json()
        
        for update in r.get("result", []):
            uid = update["update_id"]
            last_update = uid  # 🔧 فیکس اصلی
            if uid in processed:
                continue
            processed.add(uid)
            
            msg = update.get("message")
            if not msg:
                continue
            
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            chat_type = msg["chat"]["type"]
            text = msg.get("text", "")
            msg_id = msg["message_id"]
            
            # ====== پاک کردن پیام‌های تکراری ربات ======
            if user_id == int(TOKEN.split(":")[0]):  # اگه فرستنده خود ربات باشه
                # چک کن که قبلاً همین پیام رو فرستاده
                key = f"{chat_id}_{text[:50]}"
                if key in sent_cache:
                    # پیام تکراریه، پاکش کن
                    threading.Thread(target=del_msg, args=(chat_id, msg_id), daemon=True).start()
                    continue
            
            if "new_chat_members" in msg:
                if chat_type != "private":
                    for new_member in msg["new_chat_members"]:
                        uid_new = new_member.get("id")
                        if uid_new and uid_new != OWNER_ID:
                            user_name = new_member.get("first_name", "کاربر")
                            welcome_text = welcome_message(user_name)
                            send_msg(chat_id, welcome_text, reply_to=msg_id, delete_after=30)
                continue
            
            if chat_type == "private":
                if user_id == OWNER_ID:
                    if text in owner_phrases:
                        send_msg(chat_id, owner_phrases[text], reply_to=msg_id, delete_after=30)
                    elif text == "تاریخ":
                        send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=30)
                    elif text == "/start":
                        send_msg(chat_id, "✅ ربات فعال است!\n\nدستورات گروه:\nخاموشی/روشن\nسکوت/آزاد کن/بن کن\nگیف بد/استیکر بد", reply_to=msg_id, delete_after=30)
                continue
            
            if text == "تاریخ":
                send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=10)
                continue
            
            if user_id == OWNER_ID:
                if text in owner_phrases:
                    send_msg(chat_id, owner_phrases[text], reply_to=msg_id, delete_after=10)
                    continue
            
            if text:
                for w in check_words:
                    if w in text:
                        if user_id != OWNER_ID:
                            send_msg(chat_id, "آقامون نیستن 😔", reply_to=msg_id, delete_after=30)
                        break
            
            if user_id == OWNER_ID or is_admin(chat_id, user_id) or is_group_owner(chat_id, user_id):
                
                if user_id == OWNER_ID or is_group_owner(chat_id, user_id):
                    if text == "خاموشی":
                        group_locked = True
                        send_msg(chat_id, "🔒 گروه خاموش شد!", reply_to=msg_id, delete_after=60)
                        continue
                    if text == "روشن":
                        group_locked = False
                        send_msg(chat_id, "🔓 گروه روشن شد!", reply_to=msg_id, delete_after=60)
                        continue
                
                if text == "پاک" and msg.get("reply_to_message"):
                    target_msg_id = msg["reply_to_message"]["message_id"]
                    del_msg(chat_id, target_msg_id)
                    del_msg(chat_id, msg_id)
                    continue
                
                if text == "گیف بد" and msg.get("reply_to_message"):
                    gif = msg["reply_to_message"].get("animation")
                    if gif:
                        bad_gifs.append(gif["file_id"])
                        send_msg(chat_id, "✅ گیف اضافه شد!", reply_to=msg_id, delete_after=60)
                    continue
                if text == "استیکر بد" and msg.get("reply_to_message"):
                    sticker = msg["reply_to_message"].get("sticker")
                    if sticker:
                        bad_stickers.append(sticker["file_id"])
                        send_msg(chat_id, "✅ استیکر اضافه شد!", reply_to=msg_id, delete_after=60)
                    continue
                
                if text.startswith("سکوت") and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    can, error = can_moderate(chat_id, user_id, target)
                    if not can:
                        send_msg(chat_id, error, reply_to=msg_id, delete_after=60)
                        continue
                    try:
                        mins = int(text.replace("سکوت", "").strip())
                        if mins > 0:
                            mute(chat_id, target, mins)
                            send_msg(chat_id, f"🔇 {get_name(chat_id, target)} {mins} دقیقه سکوت شد! (تا {format_time(muted_users[target])})", reply_to=msg_id, delete_after=60)
                    except:
                        send_msg(chat_id, "❗ سکوت 5", reply_to=msg_id, delete_after=60)
                    continue
                
                if text == "آزاد کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    can, error = can_moderate(chat_id, user_id, target)
                    if not can:
                        send_msg(chat_id, error, reply_to=msg_id, delete_after=60)
                        continue
                    unmute(chat_id, target)
                    send_msg(chat_id, f"🔊 {get_name(chat_id, target)} آزاد شد!", reply_to=msg_id, delete_after=60)
                    continue
                
                if text == "بن کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    can, error = can_moderate(chat_id, user_id, target)
                    if not can:
                        send_msg(chat_id, error, reply_to=msg_id, delete_after=60)
                        continue
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/banChatMember", data={"chat_id": chat_id, "user_id": target}, timeout=5)
                    send_msg(chat_id, f"🚫 {get_name(chat_id, target)} بن شد!", reply_to=msg_id, delete_after=60)
                    continue
            
            if group_locked and not is_admin(chat_id, user_id) and user_id != OWNER_ID:
                del_msg(chat_id, msg_id)
                continue
            
            if user_id in muted_users and user_id != OWNER_ID:
                if datetime.now() < muted_users[user_id]:
                    del_msg(chat_id, msg_id)
                    continue
                else:
                    del muted_users[user_id]
            
            if text and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                for w in bad_words:
                    if w in text:
                        del_msg(chat_id, msg_id)
                        user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                        c = user_warnings[user_id]
                        if c == 1:
                            send_msg(chat_id, "⚠️ اخطار ۱", reply_to=msg_id, delete_after=60)
                        elif c == 2:
                            send_msg(chat_id, "⚠️⚠️ اخطار ۲", reply_to=msg_id, delete_after=60)
                        elif c == 3:
                            send_msg(chat_id, "⚠️⚠️⚠️ اخطار ۳", reply_to=msg_id, delete_after=60)
                        elif c >= 4:
                            mute(chat_id, user_id, 5)
                            send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه سکوت شد! (تا {format_time(muted_users[user_id])})", reply_to=msg_id, delete_after=60)
                            user_warnings[user_id] = 0
                        break
            
            if "animation" in msg and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    del_msg(chat_id, msg_id)
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    c = user_warnings[user_id]
                    if c >= 4:
                        mute(chat_id, user_id, 5)
                        send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه سکوت شد!", reply_to=msg_id, delete_after=60)
                        user_warnings[user_id] = 0
            
            if "sticker" in msg and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    del_msg(chat_id, msg_id)
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    c = user_warnings[user_id]
                    if c >= 4:
                        mute(chat_id, user_id, 5)
                        send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه سکوت شد!", reply_to=msg_id, delete_after=60)
                        user_warnings[user_id] = 0
        
        time.sleep(1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(2)
