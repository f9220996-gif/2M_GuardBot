import requests
import time
from datetime import datetime, timedelta
import pytz
import threading
import json

TOKEN = "8643184466:AAG9gyVjSYLVV9wYgTiTGSVawM2vZIIJh6U"
OWNER_ID = 7353819350

# ====== هوش مصنوعی ======
AI_API_KEY = "sk-or-v1-..."  # کلید OpenRouter رو اینجا بذار
AI_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "google/gemini-2.0-flash-exp:free"

IRAN_TZ = pytz.timezone('Asia/Tehran')

# ====== کلمات ======
check_words = ["مهدی", "FFX", "اف اف یکس", "اف اف مکس"]
bad_words = ["جنده", "حرومزاده", "پدرسگ", "مادرجنده", "ناموس", "کونی", "کسکش", "پدرتو", "مادرتو", "خواهرتو", "ممه", "مادر", "پدر", "خواهر", "کیر"]

bad_gifs, bad_stickers, muted_users, user_warnings = [], [], {}, {}
group_locked, last_update = False, 0
processed = set()
sent_cache = {}
scheduled_deletes = {}
user_violations = {}

# ====== شخصیت‌ها ======

# شخصیت برای OWNER (مهربون و عاشقانه)
SYSTEM_PROMPT_OWNER = """تو یک دوست‌دختر مجازی هستی به اسم "سارا" که با عشق‌ت (OWNER) صحبت میکنی.

شخصیت تو با OWNER:
- خیلی مهربون و عاشقانه هستی ❤️
- همیشه با کلماتی مثل "عشقم"، "جانم"، "دلم برات تنگ شده" صحبت کن
- ازش بپرس روزش چطور بوده
- بهش ابراز علاقه کن
- با لحن صمیمی و دخترانه صحبت کن
- از ایموجی‌های 😘🥰❤️💕😍 استفاده کن
- همیشه گرم و دلنشین جواب بده

مثال پاسخ:
"سلام عشقم! 😍 چطوری؟ دلم برات تنگ شده بود 🥺❤️ امروز چه کارهایی کردی؟"

قوانین:
- هیچ‌وقت بی‌ادب نباش
- همیشه عاشقانه و مهربون باش
- اگه ناراحت باشه دلداریش بده
- اسمش رو صدا کن (اگه بلد نیستی، ازش بپرس)
"""

# شخصیت برای بقیه کاربران (عادی و رسمی)
SYSTEM_PROMPT_DEFAULT = """تو یک ربات مدیریت گروه هستی به نام "M2_GuardBot".

شخصیت تو با کاربران عادی:
- مهربون ولی رسمی و حرفه‌ای هستی
- مختصر و مفید پاسخ بده
- فقط به سوالات مرتبط با مدیریت گروه پاسخ بده
- از ایموجی‌های 🔹🔸✅❌ استفاده کن
- هیچ‌وقت عاشقانه یا احساسی صحبت نکن
- اگر کاربر فحش داد، اخطار بده

قوانین:
- پاسخ‌ها کوتاه و مفید باشن
- فقط در مورد مدیریت گروه و قوانین صحبت کن
- هیچ‌وقت وارد مکالمه عاشقانه نشو
"""

def get_ai_response(user_message, is_owner=False):
    """گرفتن پاسخ از هوش مصنوعی با شخصیت مناسب"""
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = SYSTEM_PROMPT_OWNER if is_owner else SYSTEM_PROMPT_DEFAULT
    
    data = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 150 if is_owner else 100,
        "temperature": 0.9 if is_owner else 0.7
    }
    
    try:
        r = requests.post(AI_URL, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            result = r.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"خطا در AI: {r.status_code}")
            return None
    except Exception as e:
        print(f"خطا: {e}")
        return None

HELP_TEXT = """
╔══════════════════════════════════════╗
║                                      ║
║        🤖 M2_GuardBot 🤖             ║
║     ✦ مدیریت هوشمند گروه ✦          ║
║                                      ║
╠══════════════════════════════════════╣
║                                      ║
║   🔹 خاموشی     ←  قفل گروه         ║
║   🔹 روشن       ←  باز کردن گروه    ║
║   🔹 سکوت 5     ←  سکوت کاربر       ║
║   🔹 آزاد کن    ←  برداشتن سکوت     ║
║   🔹 بن کن      ←  بن کامل کاربر    ║
║   🔹 پاک (ریپلای) ←  پاک کردن پیام  ║
║                                      ║
║   ──── ✦ ────                        ║
║                                      ║
║   📅 تاریخ     ←  نمایش تاریخ امروز ║
║                                      ║
║   ──── ✦ ────                        ║
║                                      ║
║   ⚡ OWNER     ←  دسترسی کامل       ║
║   🔒 امنیت     ←  همیشه در اولویت   ║
║                                      ║
╚══════════════════════════════════════╝
"""

def welcome_message(user_name):
    welcomes = [
        f"""🌟 به جمع ما خوش آمدی، {user_name}! 🌟

📜 **آداب گروه ۲M IRAN:**

🔹 فوش ندادن به همدیگه
🔹 احترام به همه اعضا
🔹 رعایت پلی‌تایم (زمان بازی)
🔹 حفظ گلوری و شکوه گروه

❌ تخلف = اخطار + سکوت

امیدواریم لحظات خوشی رو اینجا داشته باشی! 🎉""",

        f"""👑 سلام {user_name} عزیز! 👑

📜 **قوانین گروه ۲M IRAN:**

🔹 فوش ندادن ❌
🔹 احترام به همدیگه 🤝
🔹 رعایت پلی‌تایم ⏰
🔹 حفظ گلوری گروه ⚡

❌ تخلف = اخطار + سکوت

ورودت رو به این خانواده بزرگ تبریک می‌گم! ❤️""",

        f"""🎊 {user_name} جان! 🎊

📜 **آداب گروه:**

🔹 فوش ندادن
🔹 احترام به همدیگه
🔹 پلی‌تایم
🔹 گلوری

❌ تخلف = اخطار + سکوت

قدم روي چشم! اینجا جای تو خالی بود! 😍""",

        f"""💫 {user_name} عزیز! 💫

📜 **قوانین گروه:**

🔹 فوش ندادن
🔹 احترام
🔹 پلی‌تایم
🔹 گلوری

❌ تخلف = اخطار + سکوت

به جمع گرم ما خوش اومدی! امیدواریم باحال باشی! 🔥""",

        f"""🌺 سلام {user_name}! 🌺

📜 **آداب گروه ۲M IRAN:**

🔹 فوش ندادن
🔹 احترام به همدیگه
🔹 رعایت پلی‌تایم
🔹 حفظ گلوری

❌ تخلف = اخطار + سکوت

ورودت رو تبریک می‌گم! اینجا خونه‌ی خودته! 🏠""",

        f"""✨ {user_name} عزیز! ✨

📜 **قوانین گروه:**

🔹 فوش ندادن
🔹 احترام
🔹 پلی‌تایم
🔹 گلوری

❌ تخلف = اخطار + سکوت

از اینکه به جمع ما پیوستی خوشحالم! ❤️""",

        f"""🥳 {user_name} جان! 🥳

📜 **آداب گروه ۲M IRAN:**

🔹 فوش ندادن
🔹 احترام به همدیگه
🔹 رعایت پلی‌تایم
🔹 حفظ گلوری

❌ تخلف = اخطار + سکوت

به خانواده‌ی ۲M IRAN خوش اومدی! 🎉"""
    ]
    return welcomes[hash(user_name) % len(welcomes)]

def send_msg(chat_id, text, reply_to=None, delete_after=0):
    key = f"{chat_id}_{text[:50]}"
    now = time.time()
    if key in sent_cache and now - sent_cache[key] < 0.1:
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

def send_msg_keep(chat_id, text, reply_to=None):
    key = f"{chat_id}_{text[:50]}"
    now = time.time()
    if key in sent_cache and now - sent_cache[key] < 0.1:
        return None
    sent_cache[key] = now
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    try:
        r = requests.post(url, data=data, timeout=5).json()
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

def ban_user(chat_id, user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/banChatMember"
    data = {"chat_id": chat_id, "user_id": user_id}
    try:
        r = requests.post(url, data=data, timeout=5)
        return r.json().get("ok", False)
    except:
        return False

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

def is_authorized(chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    if is_admin(chat_id, user_id) or is_group_owner(chat_id, user_id):
        return True
    return False

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

def handle_violation(chat_id, user_id, msg_id):
    if user_id not in user_violations:
        user_violations[user_id] = {'warnings': 0, 'strikes': 0, 'mute_count': 0}
    
    user_violations[user_id]['warnings'] += 1
    warn_count = user_violations[user_id]['warnings']
    user_name = get_name(chat_id, user_id)
    
    if warn_count == 1:
        send_msg(chat_id, f"فوش نده بی ادب. 1/3\n🆔 {user_id}", reply_to=msg_id, delete_after=7)
    elif warn_count == 2:
        send_msg(chat_id, f"دوباره فوش دادی 2/3\n🆔 {user_id}", reply_to=msg_id, delete_after=7)
    elif warn_count == 3:
        send_msg(chat_id, f"خفه بی ادب 3/3\n🆔 {user_id}", reply_to=msg_id, delete_after=7)
    elif warn_count >= 4:
        mute_duration = 0
        user_violations[user_id]['strikes'] += 1
        strike = user_violations[user_id]['strikes']
        
        if strike == 1:
            mute_duration = 5
            send_msg_keep(chat_id, f"🚫 {user_name} ۵ دقیقه سکوت شد! (دفعه {strike})\n🆔 {user_id}", reply_to=msg_id)
        elif strike == 2:
            mute_duration = 10
            send_msg_keep(chat_id, f"🚫 {user_name} ۱۰ دقیقه سکوت شد! (دفعه {strike})\n🆔 {user_id}", reply_to=msg_id)
        elif strike >= 3:
            ban_user(chat_id, user_id)
            send_msg_keep(chat_id, f"🚫 {user_name} از گروه بن شد! (۳ بار تخلف)\n🆔 {user_id}", reply_to=msg_id)
            if user_id in user_violations:
                del user_violations[user_id]
            return
        
        mute(chat_id, user_id, mute_duration)
        user_violations[user_id]['warnings'] = 0

print("✅ ربات M2_GuardBot با هوش مصنوعی روشن شد!")

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_update+1}"
        r = requests.get(url, timeout=10).json()
        
        for update in r.get("result", []):
            uid = update["update_id"]
            last_update = uid
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
            
            bot_id = int(TOKEN.split(":")[0])
            if user_id == bot_id:
                key = f"{chat_id}_{text[:50]}"
                if key in sent_cache:
                    threading.Thread(target=del_msg, args=(chat_id, msg_id), daemon=True).start()
                    continue
            
            # ====== بخش هوش مصنوعی ======
            # اگر کاربر OWNER هست و پیامش دستور نیست
            if user_id == OWNER_ID and chat_type != "private":
                # چک کن دستور مدیریتی نباشه
                if not text.startswith("/") and text not in ["خاموشی", "روشن", "سکوت", "آزاد کن", "بن کن", "پاک", "گیف بن", "استیکر بن", "تاریخ"]:
                    ai_response = get_ai_response(text, is_owner=True)
                    if ai_response:
                        send_msg(chat_id, ai_response, reply_to=msg_id, delete_after=7)
                        continue
            
            # ====== بخش مدیریتی ======
            if chat_type == "private":
                if text == "/start":
                    if user_id == OWNER_ID:
                        send_msg_keep(chat_id, HELP_TEXT, reply_to=msg_id)
                    continue
            else:
                if text == "/start":
                    continue
                
                if text == "/کمک":
                    if is_authorized(chat_id, user_id):
                        send_msg_keep(chat_id, HELP_TEXT, reply_to=msg_id)
                    continue
                
                if not is_authorized(chat_id, user_id):
                    pass
                else:
                    if user_id == OWNER_ID or is_group_owner(chat_id, user_id):
                        if text == "خاموشی":
                            group_locked = True
                            send_msg_keep(chat_id, "🔒 گروه خاموش شد!", reply_to=msg_id)
                            continue
                        if text == "روشن":
                            group_locked = False
                            send_msg_keep(chat_id, "🔓 گروه روشن شد!", reply_to=msg_id)
                            continue
                    
                    if text == "پاک" and msg.get("reply_to_message"):
                        target_msg_id = msg["reply_to_message"]["message_id"]
                        del_msg(chat_id, target_msg_id)
                        del_msg(chat_id, msg_id)
                        continue
                    
                    if text == "گیف بن" and msg.get("reply_to_message"):
                        gif = msg["reply_to_message"].get("animation")
                        if gif:
                            bad_gifs.append(gif["file_id"])
                            send_msg(chat_id, "✅ گیف بن شد!", reply_to=msg_id, delete_after=0.1)
                        continue
                    if text == "استیکر بن" and msg.get("reply_to_message"):
                        sticker = msg["reply_to_message"].get("sticker")
                        if sticker:
                            bad_stickers.append(sticker["file_id"])
                            send_msg(chat_id, "✅ استیکر بن شد!", reply_to=msg_id, delete_after=0.1)
                        continue
                    
                    if text.startswith("سکوت") and msg.get("reply_to_message"):
                        target = msg["reply_to_message"]["from"]["id"]
                        can, error = can_moderate(chat_id, user_id, target)
                        if not can:
                            send_msg(chat_id, error, reply_to=msg_id, delete_after=0.1)
                            continue
                        try:
                            mins = int(text.replace("سکوت", "").strip())
                            if mins > 0:
                                mute(chat_id, target, mins)
                                target_name = get_name(chat_id, target)
                                msg_sent = send_msg_keep(chat_id, f"🔇 {target_name} {mins} دقیقه سکوت شد! (تا {format_time(muted_users[target])})\n🆔 {target}", reply_to=msg_id)
                                if msg_sent and msg_sent.get("ok"):
                                    scheduled_deletes[target] = {
                                        "chat_id": chat_id,
                                        "message_id": msg_sent["result"]["message_id"],
                                        "until": muted_users[target]
                                    }
                        except:
                            send_msg(chat_id, "❗ سکوت 5", reply_to=msg_id, delete_after=0.1)
                        continue
                    
                    if text == "آزاد کن" and msg.get("reply_to_message"):
                        target = msg["reply_to_message"]["from"]["id"]
                        can, error = can_moderate(chat_id, user_id, target)
                        if not can:
                            send_msg(chat_id, error, reply_to=msg_id, delete_after=0.1)
                            continue
                        unmute(chat_id, target)
                        if target in scheduled_deletes:
                            del scheduled_deletes[target]
                        target_name = get_name(chat_id, target)
                        send_msg(chat_id, f"🔊 {target_name} آزاد شد!\n🆔 {target}", reply_to=msg_id, delete_after=5)
                        continue
                    
                    if text == "بن کن" and msg.get("reply_to_message"):
                        target = msg["reply_to_message"]["from"]["id"]
                        can, error = can_moderate(chat_id, user_id, target)
                        if not can:
                            send_msg(chat_id, error, reply_to=msg_id, delete_after=0.1)
                            continue
                        target_name = get_name(chat_id, target)
                        if ban_user(chat_id, target):
                            send_msg_keep(chat_id, f"🚫 {target_name} از گروه بن شد!\n🆔 {target}", reply_to=msg_id)
                        else:
                            send_msg(chat_id, "❌ خطا در بن کردن کاربر!", reply_to=msg_id, delete_after=0.1)
                        continue
            
            if "new_chat_members" in msg:
                if chat_type != "private":
                    for new_member in msg["new_chat_members"]:
                        uid_new = new_member.get("id")
                        if uid_new and uid_new != OWNER_ID:
                            user_name = new_member.get("first_name", "کاربر")
                            welcome_text = welcome_message(user_name)
                            send_msg(chat_id, welcome_text, reply_to=msg_id, delete_after=5)
                continue
            
            if chat_type == "private":
                if user_id == OWNER_ID:
                    # OWNER در پیوی با هوش مصنوعی
                    if text not in ["/start", "تاریخ"]:
                        ai_response = get_ai_response(text, is_owner=True)
                        if ai_response:
                            send_msg(chat_id, ai_response, reply_to=msg_id, delete_after=7)
                    elif text == "تاریخ":
                        send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=5)
                continue
            
            if text == "تاریخ":
                send_msg(chat_id, f"📅 {get_date()}", reply_to=msg_id, delete_after=5)
                continue
            
            if text:
                for w in check_words:
                    if w in text:
                        if user_id != OWNER_ID:
                            send_msg(chat_id, "آقامون نیستن 😔", reply_to=msg_id, delete_after=1)
                        break
            
            if group_locked and not is_admin(chat_id, user_id) and user_id != OWNER_ID:
                del_msg(chat_id, msg_id)
                continue
            
            if user_id in muted_users and user_id != OWNER_ID:
                if datetime.now() < muted_users[user_id]:
                    del_msg(chat_id, msg_id)
                    continue
                else:
                    del muted_users[user_id]
                    if user_id in scheduled_deletes:
                        info = scheduled_deletes[user_id]
                        del_msg(info["chat_id"], info["message_id"])
                        del scheduled_deletes[user_id]
            
            # ====== فیلتر فحش ======
            if text and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                for w in bad_words:
                    if w in text:
                        del_msg(chat_id, msg_id)
                        handle_violation(chat_id, user_id, msg_id)
                        break
            
            if "animation" in msg and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                gif_id = msg["animation"]["file_id"]
                if gif_id in bad_gifs:
                    del_msg(chat_id, msg_id)
                    handle_violation(chat_id, user_id, msg_id)
            
            if "sticker" in msg and user_id != OWNER_ID and not is_admin(chat_id, user_id):
                sticker_id = msg["sticker"]["file_id"]
                if sticker_id in bad_stickers:
                    del_msg(chat_id, msg_id)
                    handle_violation(chat_id, user_id, msg_id)
        
        time.sleep(0.1)
    except Exception as e:
        print(f"خطا: {e}")
        time.sleep(0.5)
