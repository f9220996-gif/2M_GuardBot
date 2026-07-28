import requests
import time
from datetime import datetime, timedelta
import pytz

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"
OWNER_ID = 7353819350
IRAN_TZ = pytz.timezone('Asia/Tehran')

# ====== کلمات ======
check_words = ["مهدی", "FFX", "اف اف یکس", "اف اف مکس"]
owner_phrases = {"سلام": "سلام عشقم خوبی؟ 😘", "اکس": "سلام عشقم خوبی؟ 😘"}

bad_words = ["جنده", "حرومزاده", "پدرسگ", "مادرجنده", "ناموس", "کونی", "کسکش", "پدرتو", "مادرتو", "خواهرتو", "ممه", "مادر", "پدر", "خواهر"]

bad_gifs, bad_stickers, muted_users, user_warnings = [], [], {}, {}
group_locked, last_update = False, 0
processed = set()  # برای جلوگیری از پردازش دوباره

def send_msg(chat_id, text, reply_to=None, delete_after=60):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, data=data).json()
        if r.get("ok") and delete_after > 0:
            mid = r["result"]["message_id"]
            time.sleep(delete_after)
            requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMessage", data={"chat_id": chat_id, "message_id": mid})
        return r
    except:
        return None

def del_msg(chat_id, msg_id):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
    except:
        pass

def mute(chat_id, user_id, minutes):
    until = datetime.now() + timedelta(minutes=minutes)
    muted_users[user_id] = until
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {"chat_id": chat_id, "user_id": user_id, "permissions": {"can_send_messages": False}, "until_date": int(until.timestamp())}
    try:
        requests.post(url, data=data)
    except:
        pass

def unmute(chat_id, user_id):
    if user_id in muted_users:
        del muted_users[user_id]
    url = f"https://api.telegram.org/bot{TOKEN}/restrictChatMember"
    data = {"chat_id": chat_id, "user_id": user_id, "permissions": {"can_send_messages": True}}
    try:
        requests.post(url, data=data)
    except:
        pass

def get_name(chat_id, user_id):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getChatMember", data={"chat_id": chat_id, "user_id": user_id}).json()
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
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getChatMember", data={"chat_id": chat_id, "user_id": user_id}).json()
        return r.get("result", {}).get("status", "member")
    except:
        return "member"

def is_admin(chat_id, user_id):
    return get_status(chat_id, user_id) in ["creator", "administrator"]

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

print("✅ ربات M2_GuardBot نسخه سبک روشن شد!")

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update+1}"
        r = requests.get(url).json()
        
        for update in r.get("result", []):
            uid = update["update_id"]
            if uid in processed:
                continue
            processed.add(uid)
            
            msg = update.get("message")
            if not msg:
                continue
            
            chat_id, user_id = msg["chat"]["id"], msg["from"]["id"]
            chat_type, text = msg["chat"]["type"], msg.get("text", "")
            msg_id = msg["message_id"]
            admin = is_admin(chat_id, user_id)
            
            # ====== پیوی فقط برای OWNER ======
            if chat_type == "private":
                if user_id == OWNER_ID:
                    if text in owner_phrases:
                        send_msg(chat_id, owner_phrases[text], reply_to=msg_id, delete_after=30)
                    elif text == "تاریخ":
                        send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=30)
                continue
            
            # ====== OWNER ======
            if user_id == OWNER_ID:
                # پاسخ به OWNER در گروه
                if text in owner_phrases:
                    send_msg(chat_id, owner_phrases[text], reply_to=msg_id, delete_after=30)
                    continue
                if text == "تاریخ":
                    send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=30)
                    continue
            
            # ====== مهدی/FFX ======
            if text:
                for w in check_words:
                    if w in text:
                        if user_id != OWNER_ID:
                            send_msg(chat_id, "آقامون نیستن 😔", reply_to=msg_id, delete_after=30)
                        break
            
            # ====== دستورات مدیریت ======
            if admin:
                if text == "خاموشی":
                    group_locked = True
                    send_msg(chat_id, "🔒 گروه خاموش شد!", reply_to=msg_id, delete_after=60)
                    continue
                if text == "روشن":
                    group_locked = False
                    send_msg(chat_id, "🔓 گروه روشن شد!", reply_to=msg_id, delete_after=60)
                    continue
                if text == "تاریخ":
                    send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=60)
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
                if text.startswith("خفه") and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    if target == OWNER_ID or (get_status(chat_id, target) in ["creator", "administrator"] and user_id != OWNER_ID):
                        send_msg(chat_id, "❌ نمی‌تونی!", reply_to=msg_id, delete_after=60)
                        continue
                    try:
                        mins = int(text.replace("خفه", "").strip())
                        if mins > 0:
                            mute(chat_id, target, mins)
                            send_msg(chat_id, f"🔇 {get_name(chat_id, target)} {mins} دقیقه خفه شد! (تا {format_time(muted_users[target])})", reply_to=msg_id, delete_after=60)
                    except:
                        send_msg(chat_id, "❗ خفه 5", reply_to=msg_id, delete_after=60)
                    continue
                if text == "آزاد کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    unmute(chat_id, target)
                    send_msg(chat_id, f"🔊 {get_name(chat_id, target)} آزاد شد!", reply_to=msg_id, delete_after=60)
                    continue
                if text == "بن کن" and msg.get("reply_to_message"):
                    target = msg["reply_to_message"]["from"]["id"]
                    if target == OWNER_ID or (get_status(chat_id, target) in ["creator", "administrator"] and user_id != OWNER_ID):
                        send_msg(chat_id, "❌ نمی‌تونی!", reply_to=msg_id, delete_after=60)
                        continue
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/banChatMember", data={"chat_id": chat_id, "user_id": target})
                    send_msg(chat_id, f"🚫 {get_name(chat_id, target)} بن شد!", reply_to=msg_id, delete_after=60)
                    continue
            
            # ====== قفل ======
            if group_locked and not admin:
                del_msg(chat_id, msg_id)
                continue
            
            # ====== خفه ======
            if user_id in muted_users and not admin:
                if datetime.now() < muted_users[user_id]:
                    del_msg(chat_id, msg_id)
                    continue
                else:
                    del muted_users[user_id]
            
            if admin:
                continue
            
            # ====== فیلتر کلمات بد ======
            if text:
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
                            send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه خفه شد! (تا {format_time(muted_users[user_id])})", reply_to=msg_id, delete_after=60)
                            user_warnings[user_id] = 0
                        break
            
            # ====== گیف/استیکر ======
            if "animation" in msg:
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    del_msg(chat_id, msg_id)
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    c = user_warnings[user_id]
                    if c >= 4:
                        mute(chat_id, user_id, 5)
                        send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه خفه شد!", reply_to=msg_id, delete_after=60)
                        user_warnings[user_id] = 0
            
            if "sticker" in msg:
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    del_msg(chat_id, msg_id)
                    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
                    c = user_warnings[user_id]
                    if c >= 4:
                        mute(chat_id, user_id, 5)
                        send_msg(chat_id, f"🚫 {get_name(chat_id, user_id)} ۵ دقیقه خفه شد!", reply_to=msg_id, delete_after=60)
                        user_warnings[user_id] = 0
        
        time.sleep(1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(2)