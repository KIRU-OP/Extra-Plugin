"""
╔══════════════════════════════════════════════════════════╗
║           🧠  ULTIMATE AI QUIZ BOT  🧠                   ║
║  All 24 OpenTDB Subjects + AI Custom Questions           ║
║  Leaderboard | Achievements | Daily Challenge | Streaks  ║
╚══════════════════════════════════════════════════════════╝
"""

import html
import json
import random
import time
import asyncio
import aiohttp
from datetime import datetime, date

from pyrogram import filters
from pyrogram.enums import PollType, ChatAction
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)

from VIPMUSIC import app

# ══════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════
last_cmd_time: dict[int, float] = {}
user_data: dict[int, dict] = {}
active_polls: dict[str, dict] = {}
daily_done: dict[int, str] = {}        # uid → date string
leaderboard_cache: list = []

COOLDOWN = 7

# ══════════════════════════════════════════════════════════════
#  ALL 24 OPENTDB CATEGORIES + AI
# ══════════════════════════════════════════════════════════════
CATEGORIES = {
    # General
    "🎭 General Knowledge":     9,
    # Entertainment
    "📚 Books":                10,
    "🎬 Film":                 11,
    "🎵 Music":                12,
    "🎭 Musicals & Theatre":   13,
    "📺 Television":           14,
    "🎮 Video Games":          15,
    "🎲 Board Games":          16,
    # Science
    "🔬 Science & Nature":     17,
    "💻 Computers":            18,
    "🧮 Mathematics":          19,
    "🔭 Mythology":            20,
    "⚽ Sports":               21,
    "🌍 Geography":            22,
    "📜 History":              23,
    "🏛️ Politics":             24,
    "🎨 Art":                  25,
    "⭐ Celebrities":          26,
    "🐾 Animals":              27,
    "🚗 Vehicles":             28,
    "📖 Comics":               29,
    "🔧 Gadgets":              30,
    "🍜 Anime & Manga":        31,
    "🃏 Cartoon & Animation":  32,
    # AI Custom
    "🤖 AI Custom (Claude)":   "ai",
}

DIFFICULTY = {
    "easy":   {"label": "🟢 Easy",   "pts": 10, "time": 30, "bonus": 0},
    "medium": {"label": "🟡 Medium", "pts": 25, "time": 22, "bonus": 5},
    "hard":   {"label": "🔴 Hard",   "pts": 50, "time": 15, "bonus": 15},
    "expert": {"label": "💀 Expert", "pts": 100, "time": 10, "bonus": 30},
}

# ══════════════════════════════════════════════════════════════
#  ACHIEVEMENTS
# ══════════════════════════════════════════════════════════════
ACHIEVEMENTS = {
    "first_blood":   ("🩸 First Blood",   "Pehla sahi jawab!",          lambda s: s["correct"] >= 1),
    "streak_3":      ("🔥 On Fire",       "3 streak!",                   lambda s: s["streak"] >= 3),
    "streak_5":      ("⚡ Lightning",     "5 streak!",                   lambda s: s["streak"] >= 5),
    "streak_10":     ("💫 Unstoppable",   "10 streak!",                  lambda s: s["streak"] >= 10),
    "century":       ("💯 Century",       "100 sahi jawab!",             lambda s: s["correct"] >= 100),
    "score_500":     ("🥉 Bronze",        "500 points!",                 lambda s: s["score"] >= 500),
    "score_1000":    ("🥈 Silver",        "1000 points!",                lambda s: s["score"] >= 1000),
    "score_5000":    ("🥇 Gold",          "5000 points!",                lambda s: s["score"] >= 5000),
    "daily_done":    ("📅 Daily Hero",    "Daily challenge complete!",   lambda s: s.get("daily_done", 0) >= 1),
    "perfect_10":    ("🎯 Perfect 10",    "10/10 accuracy ek session!",  lambda s: s.get("session_correct", 0) >= 10 and s.get("session_wrong", 0) == 0),
    "explorer":      ("🗺️ Explorer",      "10 alag categories try ki!", lambda s: len(s.get("cats_tried", set())) >= 10),
    "veteran":       ("🎖️ Veteran",       "500 questions attempt!",      lambda s: s["total"] >= 500),
}

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def get_user(uid: int) -> dict:
    if uid not in user_data:
        user_data[uid] = {
            "score": 0, "correct": 0, "total": 0,
            "streak": 0, "best_streak": 0,
            "achievements": set(),
            "cats_tried": set(),
            "daily_done": 0,
            "session_correct": 0,
            "session_wrong": 0,
            "name": "Player",
        }
    return user_data[uid]


def cooldown_left(uid: int) -> float:
    return max(0, COOLDOWN - (time.time() - last_cmd_time.get(uid, 0)))


def accuracy(st: dict) -> int:
    return round(st["correct"] / st["total"] * 100) if st["total"] else 0


def bar(pct: int, w: int = 10) -> str:
    f = round(pct / 100 * w)
    return "█" * f + "░" * (w - f)


def streak_label(n: int) -> str:
    if n >= 10: return f"{n} 💫"
    if n >= 5:  return f"{n} ⚡"
    if n >= 3:  return f"{n} 🔥"
    return str(n)


def streak_multiplier(n: int) -> float:
    if n >= 10: return 3.0
    if n >= 5:  return 2.0
    if n >= 3:  return 1.5
    return 1.0


def check_achievements(uid: int, st: dict) -> list[str]:
    """Returns list of newly unlocked achievement messages."""
    new = []
    for key, (title, desc, cond) in ACHIEVEMENTS.items():
        if key not in st["achievements"] and cond(st):
            st["achievements"].add(key)
            new.append(f"🏅 **Achievement Unlocked!**\n{title} — _{desc}_")
    return new


def rank_emoji(pos: int) -> str:
    return ["🥇", "🥈", "🥉"].get(pos - 1, f"#{pos}")

# ══════════════════════════════════════════════════════════════
#  QUESTION FETCHERS
# ══════════════════════════════════════════════════════════════
async def fetch_opentdb(cat_id: int, diff: str) -> dict | None:
    url = (
        f"https://opentdb.com/api.php"
        f"?amount=1&category={cat_id}&difficulty={diff}&type=multiple"
    )
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=7)) as r:
                data = await r.json(content_type=None)
        if data.get("response_code") == 0 and data["results"]:
            return data["results"][0]
    except Exception:
        pass
    return None


async def fetch_ai_question(diff: str) -> dict | None:
    """Generate question using Claude API."""
    topics = [
        "Indian history", "space exploration", "human biology",
        "world cuisine", "famous inventions", "cricket", "Bollywood",
        "programming languages", "geography", "mythology",
        "economics", "psychology", "chemistry", "famous leaders",
        "environmental science",
    ]
    topic = random.choice(topics)
    prompt = (
        f"Create a {diff} difficulty multiple choice quiz question about {topic}. "
        f"Return ONLY valid JSON in this exact format:\n"
        f'{{"question":"...","correct":"...","wrong":["...","...","..."]}}\n'
        f"Make it interesting, factual and educational. No markdown, no extra text."
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                resp = await r.json()
        text = resp["content"][0]["text"].strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        obj = json.loads(text)
        return {
            "question": obj["question"],
            "correct_answer": obj["correct"],
            "incorrect_answers": obj["wrong"][:3],
            "difficulty": diff,
            "category": "AI Generated",
        }
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════════════
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 Subject Choose", callback_data="quiz_subjects"),
            InlineKeyboardButton("🎲 Random Quick",   callback_data="quiz_random"),
        ],
        [
            InlineKeyboardButton("📅 Daily Challenge", callback_data="quiz_daily"),
            InlineKeyboardButton("🏆 Leaderboard",     callback_data="quiz_leaderboard"),
        ],
        [
            InlineKeyboardButton("🎖️ Achievements",   callback_data="quiz_achievements"),
            InlineKeyboardButton("📊 My Stats",        callback_data="quiz_stats"),
        ],
    ])


def subjects_kb(page: int = 0) -> InlineKeyboardMarkup:
    items = list(CATEGORIES.items())
    per_page = 12
    start = page * per_page
    chunk = items[start:start + per_page]

    rows = []
    for i in range(0, len(chunk), 2):
        row = []
        for name, cid in chunk[i:i+2]:
            row.append(InlineKeyboardButton(name, callback_data=f"qsub_{cid}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"qpage_{page-1}"))
    if start + per_page < len(items):
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"qpage_{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="quiz_main")])
    return InlineKeyboardMarkup(rows)


def difficulty_kb(cat_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Easy (+10)",    callback_data=f"qdiff_{cat_id}_easy"),
            InlineKeyboardButton("🟡 Medium (+25)",  callback_data=f"qdiff_{cat_id}_medium"),
        ],
        [
            InlineKeyboardButton("🔴 Hard (+50)",    callback_data=f"qdiff_{cat_id}_hard"),
            InlineKeyboardButton("💀 Expert (+100)", callback_data=f"qdiff_{cat_id}_expert"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="quiz_subjects")],
    ])

# ══════════════════════════════════════════════════════════════
#  /quiz COMMAND
# ══════════════════════════════════════════════════════════════
@app.on_message(filters.command(["quiz"]))
async def quiz_cmd(client, message: Message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Player"
    st   = get_user(uid)
    st["name"] = name

    wait = cooldown_left(uid)
    if wait:
        return await message.reply_text(f"⏳ **{wait:.1f}s** baad try karo bhai!")

    last_cmd_time[uid] = time.time()
    acc = accuracy(st)

    text = (
        f"🧠 **Ultimate Quiz Arena**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {name}\n"
        f"🏆 Score: **{st['score']}** pts\n"
        f"✅ {st['correct']} sahi  |  ❌ {st['total']-st['correct']} galat\n"
        f"📊 Accuracy: `{bar(acc)}` {acc}%\n"
        f"🔥 Streak: **{streak_label(st['streak'])}**  |  Best: {st['best_streak']}\n"
        f"🏅 Achievements: {len(st['achievements'])}/{len(ACHIEVEMENTS)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Kya karna chahte ho?"
    )
    await message.reply_text(text, reply_markup=main_menu_kb())


# ══════════════════════════════════════════════════════════════
#  /quizscore, /quiztop, /quizachieve
# ══════════════════════════════════════════════════════════════
@app.on_message(filters.command(["quizscore", "myscore"]))
async def score_cmd(client, message: Message):
    uid = message.from_user.id
    st  = get_user(uid)
    acc = accuracy(st)

    await message.reply_text(
        f"📊 **Tera Quiz Report Card**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Score:    `{st['score']}` pts\n"
        f"✅ Correct:  {st['correct']}\n"
        f"❌ Wrong:    {st['total'] - st['correct']}\n"
        f"📈 Accuracy: `{bar(acc)}` {acc}%\n"
        f"🔥 Streak:   {streak_label(st['streak'])}\n"
        f"⚡ Best:     {st['best_streak']}\n"
        f"🗺️ Subjects: {len(st['cats_tried'])}\n"
        f"🏅 Badges:   {len(st['achievements'])}/{len(ACHIEVEMENTS)}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


@app.on_message(filters.command(["quiztop", "leaderboard"]))
async def leaderboard_cmd(client, message: Message):
    if not user_data:
        return await message.reply_text("Abhi koi score nahi hai. /quiz se shuru karo!")

    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["score"], reverse=True)[:10]
    lines = ["🏆 **Quiz Leaderboard — Top 10**\n━━━━━━━━━━━━━━━━━━━━"]
    for i, (uid, st) in enumerate(sorted_users, 1):
        name = st.get("name", f"User {uid}")
        lines.append(f"{rank_emoji(i)} **{name}** — {st['score']} pts  ({accuracy(st)}% acc)")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    await message.reply_text("\n".join(lines))


@app.on_message(filters.command(["achievements", "badges"]))
async def achievements_cmd(client, message: Message):
    uid = message.from_user.id
    st  = get_user(uid)

    lines = ["🏅 **Teri Achievements**\n━━━━━━━━━━━━━━━━━━━━"]
    for key, (title, desc, _) in ACHIEVEMENTS.items():
        done = key in st["achievements"]
        icon = "✅" if done else "🔒"
        lines.append(f"{icon} {title} — _{desc}_")
    lines.append(f"\n**{len(st['achievements'])}/{len(ACHIEVEMENTS)}** unlock hue!")
    await message.reply_text("\n".join(lines))


@app.on_message(filters.command(["quizhelp"]))
async def quiz_help(client, message: Message):
    await message.reply_text(
        "🧠 **Ultimate Quiz Bot — Help**\n\n"
        "**Commands:**\n"
        "/quiz — Main menu\n"
        "/quizscore — Apna score\n"
        "/quiztop — Leaderboard\n"
        "/achievements — Badges dekho\n"
        "/quizhelp — Yeh message\n\n"
        "**24 Subjects:**\n"
        "General, Books, Film, Music, Theatre, TV, Video Games,\n"
        "Board Games, Science, Computers, Maths, Mythology,\n"
        "Sports, Geography, History, Politics, Art, Celebrities,\n"
        "Animals, Vehicles, Comics, Gadgets, Anime, Cartoons\n"
        "+ 🤖 AI Custom Questions (Claude se!)\n\n"
        "**Scoring:**\n"
        "🟢 Easy: 10 pts  |  🟡 Medium: 25 pts\n"
        "🔴 Hard: 50 pts  |  💀 Expert: 100 pts\n\n"
        "**Streak Bonus:**\n"
        "3x = ×1.5  |  5x = ×2.0  |  10x = ×3.0\n\n"
        "**Achievements:** 12 badges unlock karo!\n"
        "**Daily Challenge:** Har din ek special question!"
    )

# ══════════════════════════════════════════════════════════════
#  CALLBACKS — Navigation
# ══════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex(r"^quiz_main$"))
async def cb_main(client, cb: CallbackQuery):
    uid  = cb.from_user.id
    st   = get_user(uid)
    acc  = accuracy(st)
    await cb.message.edit_text(
        f"🧠 **Ultimate Quiz Arena**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Score: **{st['score']}** pts  |  Streak: {streak_label(st['streak'])}\n"
        f"📊 Accuracy: `{bar(acc)}` {acc}%\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Kya karna chahte ho?",
        reply_markup=main_menu_kb()
    )
    await cb.answer()


@app.on_callback_query(filters.regex(r"^quiz_subjects$"))
async def cb_subjects(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "📚 **Subject Choose Karo**\n"
        f"_Total {len(CATEGORIES)} subjects available hain_\n"
        "━━━━━━━━━━━━━━━━━━━━",
        reply_markup=subjects_kb(0)
    )
    await cb.answer()


@app.on_callback_query(filters.regex(r"^qpage_(\d+)$"))
async def cb_page(client, cb: CallbackQuery):
    page = int(cb.matches[0].group(1))
    await cb.message.edit_reply_markup(reply_markup=subjects_kb(page))
    await cb.answer()


@app.on_callback_query(filters.regex(r"^qsub_(.+)$"))
async def cb_subject(client, cb: CallbackQuery):
    raw = cb.matches[0].group(1)
    cat_id = raw if raw == "ai" else int(raw)
    cat_name = next((n for n, c in CATEGORIES.items() if str(c) == str(cat_id)), "Quiz")
    await cb.message.edit_text(
        f"**{cat_name}**\n\nDifficulty choose karo:",
        reply_markup=difficulty_kb(cat_id)
    )
    await cb.answer()


@app.on_callback_query(filters.regex(r"^quiz_random$"))
async def cb_random(client, cb: CallbackQuery):
    uid = cb.from_user.id
    # pick a random opentdb category
    opentdb_cats = {k: v for k, v in CATEGORIES.items() if v != "ai"}
    cat_name, cat_id = random.choice(list(opentdb_cats.items()))
    diff = random.choice(["easy", "medium", "hard"])
    await cb.answer(f"🎲 {cat_name} — {diff}!")
    await _send_question(cb.message, uid, cat_id, diff, cat_name)


@app.on_callback_query(filters.regex(r"^quiz_daily$"))
async def cb_daily(client, cb: CallbackQuery):
    uid   = cb.from_user.id
    today = str(date.today())
    if daily_done.get(uid) == today:
        await cb.answer("✅ Aaj ka daily challenge complete! Kal phir aana.", show_alert=True)
        return
    await cb.answer("📅 Daily Challenge shuru!")
    # Fixed seed for same question daily
    random.seed(int(today.replace("-", "")))
    cat_id = random.choice([c for c in CATEGORIES.values() if c != "ai"])
    diff   = random.choice(["medium", "hard"])
    random.seed()  # reset seed
    cat_name = next((n for n, c in CATEGORIES.items() if c == cat_id), "Quiz")
    daily_done[uid] = today
    st = get_user(uid)
    st["daily_done"] = st.get("daily_done", 0) + 1
    await _send_question(cb.message, uid, cat_id, diff, cat_name, is_daily=True)


@app.on_callback_query(filters.regex(r"^quiz_leaderboard$"))
async def cb_leaderboard(client, cb: CallbackQuery):
    if not user_data:
        await cb.answer("Koi data nahi!", show_alert=True)
        return
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["score"], reverse=True)[:10]
    lines = ["🏆 **Top 10 Players**\n━━━━━━━━━━━━━━━━━━━━"]
    for i, (uid, st) in enumerate(sorted_users, 1):
        name = st.get("name", f"User{uid}")[:20]
        lines.append(f"{rank_emoji(i)} **{name}** — {st['score']} pts")
    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="quiz_main")]])
    )
    await cb.answer()


@app.on_callback_query(filters.regex(r"^quiz_achievements$"))
async def cb_achievements(client, cb: CallbackQuery):
    uid = cb.from_user.id
    st  = get_user(uid)
    lines = [f"🏅 **Achievements** ({len(st['achievements'])}/{len(ACHIEVEMENTS)})\n━━━━━━━━━━━━━━━━━━━━"]
    for key, (title, desc, _) in ACHIEVEMENTS.items():
        done = key in st["achievements"]
        lines.append(f"{'✅' if done else '🔒'} {title}")
    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="quiz_main")]])
    )
    await cb.answer()


@app.on_callback_query(filters.regex(r"^quiz_stats$"))
async def cb_stats(client, cb: CallbackQuery):
    uid = cb.from_user.id
    st  = get_user(uid)
    acc = accuracy(st)
    await cb.message.edit_text(
        f"📊 **My Stats**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Score:     {st['score']}\n"
        f"✅ Correct:   {st['correct']}\n"
        f"❌ Wrong:     {st['total'] - st['correct']}\n"
        f"📈 Accuracy:  {acc}%\n"
        f"🔥 Streak:    {streak_label(st['streak'])}\n"
        f"⚡ Best:      {st['best_streak']}\n"
        f"🗺️ Subjects:  {len(st['cats_tried'])}\n"
        f"📅 Daily:     {st.get('daily_done', 0)} done\n"
        f"🏅 Badges:    {len(st['achievements'])}/{len(ACHIEVEMENTS)}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="quiz_main")]])
    )
    await cb.answer()


# ══════════════════════════════════════════════════════════════
#  DIFFICULTY CALLBACK → FETCH + SEND POLL
# ══════════════════════════════════════════════════════════════
@app.on_callback_query(filters.regex(r"^qdiff_(.+)_(\w+)$"))
async def cb_difficulty(client, cb: CallbackQuery):
    raw   = cb.matches[0].group(1)
    diff  = cb.matches[0].group(2)
    uid   = cb.from_user.id

    wait = cooldown_left(uid)
    if wait:
        await cb.answer(f"⏳ {wait:.1f}s baad!", show_alert=True)
        return

    last_cmd_time[uid] = time.time()
    cat_id   = raw if raw == "ai" else int(raw)
    cat_name = next((n for n, c in CATEGORIES.items() if str(c) == str(cat_id)), "Quiz")

    await cb.answer()
    await _send_question(cb.message, uid, cat_id, diff, cat_name)


# ══════════════════════════════════════════════════════════════
#  CORE: FETCH QUESTION + SEND POLL
# ══════════════════════════════════════════════════════════════
async def _send_question(
    message: Message,
    uid: int,
    cat_id,
    diff: str,
    cat_name: str,
    is_daily: bool = False,
):
    cfg = DIFFICULTY.get(diff, DIFFICULTY["medium"])
    st  = get_user(uid)

    # Update cats tried
    st["cats_tried"].add(str(cat_id))

    # Streak multiplier
    mult = streak_multiplier(st["streak"])
    pts  = round(cfg["pts"] * mult)

    bonus_txt = ""
    if mult > 1:
        bonus_txt = f"  ×{mult:.1f} streak bonus"

    daily_txt = "  📅 **DAILY CHALLENGE**\n" if is_daily else ""

    loading_msg = (
        f"{daily_txt}"
        f"⏳ {cat_name} — {cfg['label']}\n"
        f"💎 {pts} pts{bonus_txt}\n"
        f"_Fetching question..._"
    )

    try:
        await message.edit_text(loading_msg)
    except Exception:
        pass

    await app.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Fetch question
    if cat_id == "ai":
        q = await fetch_ai_question(diff if diff != "expert" else "hard")
    else:
        q = await fetch_opentdb(cat_id, diff if diff != "expert" else "hard")
        # Retry once on failure
        if not q:
            await asyncio.sleep(1)
            q = await fetch_opentdb(cat_id, "medium")

    if not q:
        try:
            await message.edit_text(
                "❌ Question fetch nahi hua. Retry karo!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Retry", callback_data=f"qdiff_{cat_id}_{diff}"),
                    InlineKeyboardButton("🔙 Menu", callback_data="quiz_main"),
                ]])
            )
        except Exception:
            pass
        return

    question    = html.unescape(q["question"])
    correct_ans = html.unescape(q["correct_answer"])
    options     = [html.unescape(a) for a in q["incorrect_answers"]] + [correct_ans]
    random.shuffle(options)
    correct_idx = options.index(correct_ans)

    # Explanation text for poll
    explanation = f"📚 {cat_name} | {cfg['label']}"
    if is_daily:
        explanation = "📅 Daily Challenge — " + explanation

    # Header message
    header = (
        f"{daily_txt}"
        f"🧠 **{cat_name}**\n"
        f"{cfg['label']}  |  ⏱ {cfg['time']}s  |  💎 {pts} pts{bonus_txt}"
    )
    try:
        await message.edit_text(header)
    except Exception:
        pass

    poll_msg = await app.send_poll(
        chat_id=message.chat.id,
        question=question[:255],
        options=[o[:100] for o in options[:4]],
        is_anonymous=False,
        type=PollType.QUIZ,
        correct_option_id=correct_idx,
        explanation=explanation[:200],
        open_period=cfg["time"],
    )

    if poll_msg.poll:
        active_polls[poll_msg.poll.id] = {
            "correct_id": correct_idx,
            "user_id":    uid,
            "pts":        pts,
            "cat":        cat_name,
            "diff":       diff,
            "chat_id":    message.chat.id,
            "is_daily":   is_daily,
        }


# ══════════════════════════════════════════════════════════════
#  POLL ANSWER HANDLER
# ══════════════════════════════════════════════════════════════
@app.on_poll_answer()
async def on_poll_answer(client, poll_answer):
    pid    = poll_answer.poll_id
    uid    = poll_answer.user.id
    name   = poll_answer.user.first_name or "Player"

    if pid not in active_polls:
        return

    info = active_polls.pop(pid)
    st   = get_user(uid)
    st["name"]  = name
    st["total"] += 1

    chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    won    = (chosen == info["correct_id"])

    if won:
        st["correct"]      += 1
        st["streak"]       += 1
        st["score"]        += info["pts"]
        st["session_correct"] = st.get("session_correct", 0) + 1
        st["best_streak"]  = max(st["best_streak"], st["streak"])

        sl  = streak_label(st["streak"])
        acc = accuracy(st)
        msg = (
            f"✅ **{name}** — Sahi jawab!\n"
            f"💎 +{info['pts']} pts  |  🔥 Streak: {sl}\n"
            f"🏆 Total: {st['score']} pts  |  📊 {acc}%"
        )
    else:
        st["streak"]       = 0
        st["session_wrong"] = st.get("session_wrong", 0) + 1
        msg = (
            f"❌ **{name}** — Galat!\n"
            f"💔 Streak reset  |  🏆 {st['score']} pts\n"
            f"💡 /quiz se aur practice karo!"
        )

    # Check achievements
    new_achievements = check_achievements(uid, st)

    try:
        await app.send_message(info["chat_id"], msg)
        for ach in new_achievements:
            await asyncio.sleep(0.5)
            await app.send_message(info["chat_id"], ach)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  MODULE META
# ══════════════════════════════════════════════════════════════
__MODULE__ = "Quiz"
__HELP__ = (
    "/quiz — Ultimate AI Quiz (24 subjects + AI)\n"
    "/quizscore — Apna score\n"
    "/quiztop — Leaderboard\n"
    "/achievements — Badges\n"
    "/quizhelp — Full help"
)
