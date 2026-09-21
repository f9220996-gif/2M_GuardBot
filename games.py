# -*- coding: utf-8 -*-
"""
چند بازی کوچیک و فان برای وقت بیکاری در گروه:
تاس، شیر یا خط، سنگ‌کاغذقیچی (یک راند، با ربات یا دو نفره، با دکمه)،
دوز (XO با ربات تو سه سطح، یا دو نفره)
"""

import random
import time
from functools import lru_cache

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes


async def cmd_tas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پرتاب تاس واقعی تلگرام (انیمیشن دار)"""
    await update.effective_message.reply_dice(emoji="🎲")


async def cmd_shir_khat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["شیر 🦁", "خط 〰️"])
    await update.effective_message.reply_text(f"🪙 نتیجه: {result}")


# ---------------------------------------------------------------------------
# سنگ‌کاغذقیچی: یک راند.
# ریپلای روی پیام کسی = چالش مستقیم با همون شخص. بدون ریپلای = بازی با ربات.
# اگه کسی جواب نده، بازی بعد از RPS_TIMEOUT ثانیه خودکار منقضی می‌شه.
# ---------------------------------------------------------------------------

CHOICES = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}
RPS_TIMEOUT = 120


def _beats(a, b):
    return (
        (a == "سنگ" and b == "قیچی") or
        (a == "کاغذ" and b == "سنگ") or
        (a == "قیچی" and b == "کاغذ")
    )


def _rps_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨", callback_data="rps_pick:سنگ"),
        InlineKeyboardButton("📄", callback_data="rps_pick:کاغذ"),
        InlineKeyboardButton("✂️", callback_data="rps_pick:قیچی"),
    ]])


async def cmd_sang_kaghaz_gheychi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اگه ریپلای روی پیام یه نفر باشه، مستقیم باهاش چالش شروع می‌شه.
    اگه بدون ریپلای باشه، بازی با خودِ ربات شروع می‌شه.
    """
    message = update.effective_message
    user = update.effective_user

    existing = context.chat_data.get("rps_game")
    if existing and existing.get("status") == "playing":
        if time.time() - existing.get("created_at", 0) < RPS_TIMEOUT:
            await message.reply_text("⚠️ یه بازی سنگ‌کاغذقیچی از قبل تو این گروه در حال اجراست.")
            return
        # بازی قبلی جوابی نگرفته و منقضی شده
        context.chat_data["rps_game"] = None

    reply_target = message.reply_to_message.from_user if message.reply_to_message else None

    if reply_target and not reply_target.is_bot:
        if reply_target.id == user.id:
            await message.reply_text("نمی‌تونی با خودت بازی کنی! 😄")
            return

        context.chat_data["rps_game"] = {
            "mode": "vs_player",
            "player1_id": user.id,
            "player1_name": user.full_name,
            "player2_id": reply_target.id,
            "player2_name": reply_target.full_name,
            "choices": {},
            "status": "playing",
            "created_at": time.time(),
        }
        await message.reply_text(
            f"✂️📄🪨 {user.full_name} با {reply_target.full_name} به چالش سنگ‌کاغذقیچی افتاد!\n\n"
            "هردو نفر دکمه‌ی انتخابشون رو بزنن:",
            reply_markup=_rps_keyboard()
        )
        return

    # بدون ریپلای -> بازی با ربات
    context.chat_data["rps_game"] = {
        "mode": "vs_bot",
        "player1_id": user.id,
        "player1_name": user.full_name,
        "choices": {},
        "status": "playing",
        "created_at": time.time(),
    }
    await message.reply_text(
        f"✂️📄🪨 {user.full_name}، با من بازی کن! انتخابتو بزن:",
        reply_markup=_rps_keyboard()
    )


async def rps_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, choice = query.data.split(":")
    game = context.chat_data.get("rps_game")
    user = update.effective_user

    if not game or game.get("status") != "playing":
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return

    if time.time() - game.get("created_at", 0) > RPS_TIMEOUT:
        context.chat_data["rps_game"] = None
        await query.answer("⌛ این بازی منقضی شده.", show_alert=True)
        try:
            await query.edit_message_text("⌛ بازی سنگ‌کاغذقیچی به‌خاطر بی‌جوابی بسته شد.")
        except Exception:
            pass
        return

    # ===== حالت بازی با ربات =====
    if game["mode"] == "vs_bot":
        if user.id != game["player1_id"]:
            await query.answer("⛔️ این بازی مال تو نیست.", show_alert=True)
            return

        bot_choice = random.choice(list(CHOICES.keys()))
        await query.answer()

        if choice == bot_choice:
            result_line = f"مساوی شدیم! هر دو {CHOICES[choice]} انتخاب کردیم. 🤝"
        elif _beats(choice, bot_choice):
            result_line = f"🎉 بردی! ({CHOICES[choice]} در برابر {CHOICES[bot_choice]})"
        else:
            result_line = f"😅 باختی! ({CHOICES[bot_choice]} در برابر {CHOICES[choice]})"

        await query.edit_message_text(
            f"✂️📄🪨 نتیجه\n\n"
            f"{game['player1_name']}: {CHOICES[choice]}\n"
            f"من: {CHOICES[bot_choice]}\n\n"
            f"{result_line}"
        )
        context.chat_data["rps_game"] = None
        return

    # ===== حالت دو نفره =====
    if user.id not in (game["player1_id"], game["player2_id"]):
        await query.answer("⛔️ تو تو این بازی نیستی.", show_alert=True)
        return

    if user.id in game["choices"]:
        await query.answer("قبلاً انتخاب کردی، منتظر حریفت باش.", show_alert=True)
        return

    game["choices"][user.id] = choice
    await query.answer("✅ انتخابت ثبت شد.")

    if len(game["choices"]) < 2:
        other_name = (
            game["player2_name"] if user.id == game["player1_id"] else game["player1_name"]
        )
        try:
            await query.edit_message_text(
                f"✂️📄🪨 {game['player1_name']} 🆚 {game['player2_name']}\n\n"
                f"✅ یک نفر انتخابش رو کرد.\n"
                f"⏳ منتظر جواب {other_name}...",
                reply_markup=_rps_keyboard()
            )
        except Exception:
            pass
        return

    c1 = game["choices"][game["player1_id"]]
    c2 = game["choices"][game["player2_id"]]

    if c1 == c2:
        result_line = f"مساوی شد! هر دو {CHOICES[c1]} انتخاب کردن. 🤝"
    elif _beats(c1, c2):
        result_line = f"🏆 {game['player1_name']} برد! ({CHOICES[c1]} در برابر {CHOICES[c2]})"
    else:
        result_line = f"🏆 {game['player2_name']} برد! ({CHOICES[c2]} در برابر {CHOICES[c1]})"

    await query.edit_message_text(
        f"✂️📄🪨 نتیجه\n\n"
        f"{game['player1_name']}: {CHOICES[c1]}\n"
        f"{game['player2_name']}: {CHOICES[c2]}\n\n"
        f"{result_line}"
    )
    context.chat_data["rps_game"] = None


# ---------------------------------------------------------------------------
# دوز (XO)
#   «دوز»                      ← بازی با ربات (اول سطح رو انتخاب می‌کنی: آسان / متوسط / سخت)
#   «دوز» + ریپلای روی یه نفر  ← بازی دو نفره؛ شروع‌کننده ❌ و حریف ⭕
# تو بازی با ربات، تو ⭕ هستی و ربات (❌) اول شروع می‌کنه.
# هر بازی به آیدی پیام خودش وصله، پس تو یه گروه چند بازی هم‌زمان مشکلی ندارن.
# ---------------------------------------------------------------------------

DOOZ_EMPTY = "⬜"
DOOZ_SYMBOL = {"X": "❌", "O": "⭕"}
DOOZ_LEVELS = {"easy": "آسان 😊", "medium": "متوسط 😐", "hard": "سخت 😈"}
DOOZ_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]
DOOZ_IDLE_TIMEOUT = 600        # اگه ۱۰ دقیقه حرکتی نشه، بازی بسته می‌شه
DOOZ_MAX_GAMES_PER_CHAT = 12   # حداکثر بازی هم‌زمان تو هر گروه


def _dooz_winner(board):
    for a, b, c in DOOZ_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def _dooz_result(board):
    """'X' یا 'O' اگه برنده داشت، 'draw' اگه مساوی شد، وگرنه None"""
    w = _dooz_winner(board)
    if w:
        return w
    if all(board):
        return "draw"
    return None


def _empty_cells(board):
    return [i for i, v in enumerate(board) if not v]


def _find_win_move(board, who):
    for i in _empty_cells(board):
        trial = list(board)
        trial[i] = who
        if _dooz_winner(trial) == who:
            return i
    return None


@lru_cache(maxsize=None)
def _minimax(board: tuple, turn: str, me: str) -> int:
    """امتیاز وضعیت برای بازیکن me؛ برد سریع‌تر و باخت دیرتر امتیاز بهتری داره"""
    w = _dooz_winner(board)
    bonus = 1 + board.count("")
    if w == me:
        return bonus
    if w:
        return -bonus
    empties = [i for i, v in enumerate(board) if not v]
    if not empties:
        return 0
    other = "O" if turn == "X" else "X"
    scores = []
    for i in empties:
        trial = list(board)
        trial[i] = turn
        scores.append(_minimax(tuple(trial), other, me))
    return max(scores) if turn == me else min(scores)


def _dooz_bot_move(board, level, me="X", opp="O"):
    empties = _empty_cells(board)
    if level == "easy":
        return random.choice(empties)

    if level == "medium":
        move = _find_win_move(board, me)
        if move is None:
            move = _find_win_move(board, opp)
        if move is not None:
            return move
        if 4 in empties and random.random() < 0.6:
            return 4
        return random.choice(empties)

    # سخت: بازی کامل (بردنش ممکن نیست، بهترین نتیجه‌ی تو مساویه)
    best, moves = None, []
    for i in empties:
        trial = list(board)
        trial[i] = me
        score = _minimax(tuple(trial), opp, me)
        if best is None or score > best:
            best, moves = score, [i]
        elif score == best:
            moves.append(i)
    return random.choice(moves)


def _dooz_keyboard(board):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            label = DOOZ_SYMBOL[board[i]] if board[i] else DOOZ_EMPTY
            row.append(InlineKeyboardButton(label, callback_data=f"dooz:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _dooz_level_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(DOOZ_LEVELS["easy"], callback_data="dooz_lvl:easy"),
        InlineKeyboardButton(DOOZ_LEVELS["medium"], callback_data="dooz_lvl:medium"),
        InlineKeyboardButton(DOOZ_LEVELS["hard"], callback_data="dooz_lvl:hard"),
    ]])


def _dooz_text(game, result=None):
    players = game["players"]
    if game["mode"] == "bot":
        name = players["O"]["name"]
        lines = [
            f"🎮 دوز با ربات · {DOOZ_LEVELS[game['level']]}",
            "",
            f"شما بازی می‌کنید به عنوان {DOOZ_SYMBOL['O']}",
        ]
        if result == "O":
            lines.append(f"\n🎉 {name} برد!")
        elif result == "X":
            lines.append("\n😈 من بردم!")
        elif result == "draw":
            lines.append("\n🤝 مساوی شد!")
        else:
            lines.append(f"نوبت {name} 👈")
        return "\n".join(lines)

    lines = [
        "🎮 دوز",
        f"{DOOZ_SYMBOL['X']} {players['X']['name']}  🆚  {DOOZ_SYMBOL['O']} {players['O']['name']}",
        "",
    ]
    if result in ("X", "O"):
        lines.append(f"🏆 {players[result]['name']} برد!")
    elif result == "draw":
        lines.append("🤝 مساوی شد!")
    else:
        turn = game["turn"]
        lines.append(f"نوبت {DOOZ_SYMBOL[turn]} {players[turn]['name']} 👈")
    return "\n".join(lines)


def _dooz_store(context):
    return context.chat_data.setdefault("dooz_games", {})


def _dooz_prune(games):
    """بازی‌های خیلی قدیمی رو از حافظه پاک می‌کنه و تعداد بازی‌ها رو محدود نگه می‌داره"""
    now = time.time()
    for mid in [m for m, g in games.items() if now - g["updated_at"] > DOOZ_IDLE_TIMEOUT * 3]:
        games.pop(mid, None)
    while len(games) >= DOOZ_MAX_GAMES_PER_CHAT:
        oldest = min(games, key=lambda m: games[m]["updated_at"])
        games.pop(oldest, None)


async def _safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        pass  # مثلاً «message is not modified»


async def _dooz_expire(query, games):
    games.pop(query.message.message_id, None)
    await query.answer("⌛ این بازی به‌خاطر بی‌تحرکی بسته شده.", show_alert=True)
    await _safe_edit(query, "⌛ بازی دوز به‌خاطر بی‌تحرکی بسته شد.")


async def cmd_dooz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    games = _dooz_store(context)
    _dooz_prune(games)
    now = time.time()

    target = message.reply_to_message.from_user if message.reply_to_message else None

    # ===== دو نفره =====
    if target and not target.is_bot:
        if target.id == user.id:
            await message.reply_text("نمی‌تونی با خودت بازی کنی! 😄")
            return
        game = {
            "mode": "player",
            "board": [""] * 9,
            "turn": "X",
            "status": "playing",
            "players": {
                "X": {"id": user.id, "name": user.full_name},
                "O": {"id": target.id, "name": target.full_name},
            },
            "created_at": now,
            "updated_at": now,
        }
        sent = await message.reply_text(_dooz_text(game), reply_markup=_dooz_keyboard(game["board"]))
        games[sent.message_id] = game
        return

    # ===== با ربات: اول سطح رو انتخاب کن =====
    game = {
        "mode": "bot",
        "status": "choose_level",
        "owner_id": user.id,
        "owner_name": user.full_name,
        "created_at": now,
        "updated_at": now,
    }
    sent = await message.reply_text(
        f"🎮 دوز با ربات\n\n{user.full_name}، سطح بازی رو انتخاب کن:",
        reply_markup=_dooz_level_keyboard(),
    )
    games[sent.message_id] = game


async def dooz_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    level = query.data.split(":")[1]
    user = update.effective_user
    games = _dooz_store(context)
    game = games.get(query.message.message_id)

    if not game or game.get("status") != "choose_level" or level not in DOOZ_LEVELS:
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return
    if user.id != game["owner_id"]:
        await query.answer("⛔️ این بازی مال تو نیست.", show_alert=True)
        return
    if time.time() - game["updated_at"] > DOOZ_IDLE_TIMEOUT:
        await _dooz_expire(query, games)
        return

    board = [""] * 9
    game.update({
        "level": level,
        "board": board,
        "turn": "O",
        "status": "playing",
        "players": {
            "X": {"id": None, "name": "ربات"},
            "O": {"id": user.id, "name": user.full_name},
        },
        "updated_at": time.time(),
    })
    # ربات (❌) اولین حرکت رو می‌زنه
    board[_dooz_bot_move(board, level)] = "X"

    await query.answer()
    await _safe_edit(query, _dooz_text(game), _dooz_keyboard(board))


async def dooz_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    idx = int(query.data.split(":")[1])
    user = update.effective_user
    games = _dooz_store(context)
    message_id = query.message.message_id
    game = games.get(message_id)

    if not game or game.get("status") != "playing":
        await query.answer("این بازی دیگه فعال نیست.", show_alert=True)
        return
    if time.time() - game["updated_at"] > DOOZ_IDLE_TIMEOUT:
        await _dooz_expire(query, games)
        return

    board = game["board"]

    if game["mode"] == "bot":
        if user.id != game["players"]["O"]["id"]:
            await query.answer("⛔️ این بازی مال تو نیست.", show_alert=True)
            return
        if board[idx]:
            await query.answer("این خونه پره!", show_alert=True)
            return
        board[idx] = "O"
        result = _dooz_result(board)
        if not result:
            board[_dooz_bot_move(board, game["level"])] = "X"
            result = _dooz_result(board)
    else:
        turn = game["turn"]
        if user.id != game["players"][turn]["id"]:
            in_game = user.id in (game["players"]["X"]["id"], game["players"]["O"]["id"])
            await query.answer("⏳ نوبت تو نیست." if in_game else "⛔️ تو تو این بازی نیستی.", show_alert=True)
            return
        if board[idx]:
            await query.answer("این خونه پره!", show_alert=True)
            return
        board[idx] = turn
        result = _dooz_result(board)
        if not result:
            game["turn"] = "O" if turn == "X" else "X"

    game["updated_at"] = time.time()
    await query.answer()
    await _safe_edit(query, _dooz_text(game, result), _dooz_keyboard(board))
    if result:
        games.pop(message_id, None)
