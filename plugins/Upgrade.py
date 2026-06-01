import asyncio
import os
import shutil
import time
import zipfile

from github import Github, GithubException
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import Message

from VIPMUSIC import app

# --- CONFIG ---
try:
    try:
        from config import MONGO_DB_URI as MONGO_DB_URL
    except ImportError:
        from config import MONGO_DB_URL
except ImportError:
    MONGO_DB_URL = None

MAX_ZIP_MB = 50

# --- DATABASE SETUP ---
tokens_col = None
pending_col = None
if MONGO_DB_URL:
    mongo_client = AsyncIOMotorClient(MONGO_DB_URL)
    db = mongo_client["GitHubPublicBot"]
    tokens_col = db["user_tokens"]
    pending_col = db["pending_uploads"]  # stores repo name, old word, new word temporarily

# --- HELP TEXT ---
HELP_TEXT = """
🚀 **GITHUB REPO UPGRADER BOT**
━━━━━━━━━━━━━━━━━━━━━━
Upload aur refactor karo repositories (imports/folder names automatically replace hote hain).

🔐 **SETUP:**
• `/settoken <token>` — GitHub Personal Access Token save karo
• `/deltoken` — Token delete karo

📤 **UPLOAD COMMANDS (yeh teen commands use karo):**

**Step 1:** `/set_repo <repo_naam>`
➡️ GitHub repo ka naam set karo
Example: `/set_repo MyNewBot`

**Step 2:** `/set_replace <purana_word> <naya_word>`
➡️ Kaunsa word replace hoga set karo
Example: `/set_replace VIPMUSIC ALEX_MUSIC`

**Step 3:** `/upload_zip`
➡️ ZIP file ke reply mein yeh command likho — upload ho jayega!

━━━━━━━━━━━━━━━━━━━━━━
"""

REFACTOR_EXTENSIONS = {
    ".py", ".txt", ".md", ".yml", ".yaml",
    ".conf", ".env", ".json", ".toml", ".ini",
}


# --- HELPERS ---

async def get_token(user_id: int) -> str | None:
    if not tokens_col:
        return None
    res = await tokens_col.find_one({"user_id": user_id})
    return res["token"] if res else None


async def get_pending(user_id: int) -> dict | None:
    if not pending_col:
        return None
    return await pending_col.find_one({"user_id": user_id})


async def set_pending(user_id: int, data: dict):
    if not pending_col:
        return
    await pending_col.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True,
    )


async def clear_pending(user_id: int):
    if not pending_col:
        return
    await pending_col.delete_one({"user_id": user_id})


def _safe_extract(zip_path: str, dest: str) -> None:
    """Extract a ZIP while guarding against path-traversal attacks."""
    dest = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            target = os.path.realpath(os.path.join(dest, member))
            if os.path.commonpath([dest, target]) != dest:
                raise ValueError(f"Unsafe ZIP path detected: {member}")
        zf.extractall(dest)


# --- HANDLERS ---

@app.on_message(filters.command(["start", "help"]))
async def help_handler(_, message: Message):
    await message.reply_text(HELP_TEXT)


# ── STEP 1: Repo naam set karo ──────────────────────────────────────────────

@app.on_message(filters.command("set_repo"))
async def set_repo_cmd(_, message: Message):
    if not pending_col:
        return await message.reply_text("❌ Database configured nahi hai.")

    if len(message.command) < 2:
        return await message.reply_text(
            "❌ **Repo naam dena bhool gaye!**\n\n"
            "✅ **Sahi tarika:**\n"
            "`/set_repo <repo_naam>`\n\n"
            "📌 **Example:**\n"
            "`/set_repo MyNewBot`"
        )

    repo_name = message.command[1]
    await set_pending(message.from_user.id, {"repo_name": repo_name})
    await message.reply_text(
        f"✅ **Repo naam set ho gaya!**\n\n"
        f"📦 **Repo:** `{repo_name}`\n\n"
        f"➡️ **Ab Step 2 karo:**\n"
        f"`/set_replace <purana_word> <naya_word>`\n\n"
        f"📌 **Example:**\n"
        f"`/set_replace VIPMUSIC ALEX_MUSIC`"
    )


# ── STEP 2: Replace words set karo ─────────────────────────────────────────

@app.on_message(filters.command("set_replace"))
async def set_replace_cmd(_, message: Message):
    if not pending_col:
        return await message.reply_text("❌ Database configured nahi hai.")

    pending = await get_pending(message.from_user.id)
    if not pending or not pending.get("repo_name"):
        return await message.reply_text(
            "⚠️ **Pehle repo naam set karo!**\n\n"
            "➡️ `/set_repo <repo_naam>`\n"
            "📌 Example: `/set_repo MyNewBot`"
        )

    if len(message.command) < 3:
        return await message.reply_text(
            "❌ **Dono words dene hain!**\n\n"
            "✅ **Sahi tarika:**\n"
            "`/set_replace <purana_word> <naya_word>`\n\n"
            "📌 **Example:**\n"
            "`/set_replace VIPMUSIC ALEX_MUSIC`"
        )

    old_word = message.command[1]
    new_word = message.command[2]
    await set_pending(message.from_user.id, {"old_word": old_word, "new_word": new_word})

    await message.reply_text(
        f"✅ **Replace words set ho gaye!**\n\n"
        f"📦 **Repo:** `{pending['repo_name']}`\n"
        f"🔄 **Replace:** `{old_word}` ➔ `{new_word}`\n\n"
        f"➡️ **Ab Step 3 (last step) karo:**\n"
        f"ZIP file bhejo aur uske reply mein likho:\n"
        f"`/upload_zip`"
    )


# ── STEP 3: ZIP upload karo ─────────────────────────────────────────────────

@app.on_message(filters.command("upload_zip"))
async def upload_zip_cmd(_, message: Message):
    user_id = message.from_user.id

    # Token check
    token = await get_token(user_id)
    if not token:
        return await message.reply_text(
            "🔑 **Pehle GitHub token set karo:**\n"
            "`/settoken <your_github_token>`"
        )

    # Pending data check
    pending = await get_pending(user_id)
    if not pending or not pending.get("repo_name"):
        return await message.reply_text(
            "⚠️ **Pehle repo naam set karo!**\n\n"
            "➡️ `/set_repo <repo_naam>`\n"
            "📌 Example: `/set_repo MyNewBot`"
        )
    if not pending.get("old_word") or not pending.get("new_word"):
        return await message.reply_text(
            "⚠️ **Pehle replace words set karo!**\n\n"
            "➡️ `/set_replace <purana_word> <naya_word>`\n"
            "📌 Example: `/set_replace VIPMUSIC ALEX_MUSIC`"
        )

    # ZIP file check
    if not (message.reply_to_message and message.reply_to_message.document):
        return await message.reply_text(
            "❌ **ZIP file pe reply karke yeh command likho!**\n\n"
            "📌 Tarika:\n"
            "1. ZIP file bhejo chat mein\n"
            "2. Usi ZIP pe reply karo\n"
            "3. Reply mein likho `/upload_zip`"
        )

    doc = message.reply_to_message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".zip"):
        return await message.reply_text("❌ File **.zip** format mein honi chahiye.")

    if doc.file_size and doc.file_size > MAX_ZIP_MB * 1024 * 1024:
        return await message.reply_text(
            f"❌ ZIP bahut bada hai! Maximum size **{MAX_ZIP_MB} MB** hai."
        )

    repo_name = pending["repo_name"]
    old_word  = pending["old_word"]
    new_word  = pending["new_word"]

    status = await message.reply_text(
        f"⏳ **Shuru ho raha hai...**\n"
        f"📦 Repo: `{repo_name}`\n"
        f"🔄 Replace: `{old_word}` ➔ `{new_word}`"
    )

    extract_dir = f"work_{user_id}_{int(time.time())}"
    file_path: str | None = None

    try:
        # GitHub setup
        g    = await asyncio.to_thread(Github, token)
        user = await asyncio.to_thread(g.get_user)

        try:
            repo = await asyncio.to_thread(user.get_repo, repo_name)
        except GithubException:
            await status.edit(f"🔨 Repo `{repo_name}` ban raha hai...")
            repo = await asyncio.to_thread(user.create_repo, repo_name, auto_init=True)
            await asyncio.sleep(2)

        # Download & extract
        await status.edit("📥 **ZIP download ho raha hai...**")
        file_path = await message.reply_to_message.download()
        os.makedirs(extract_dir, exist_ok=True)
        _safe_extract(file_path, extract_dir)

        await status.edit("🚀 **Files refactor ho rahi hain aur GitHub pe upload ho rahi hain...**")

        entries     = os.listdir(extract_dir)
        upload_from = (
            os.path.join(extract_dir, entries[0])
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0]))
            else extract_dir
        )

        count  = 0
        errors = 0

        for root, _dirs, files in os.walk(upload_from):
            for filename in files:
                local_path = os.path.join(root, filename)

                try:
                    with open(local_path, "rb") as fh:
                        content = fh.read()
                except OSError as exc:
                    print(f"[read error] {local_path}: {exc}")
                    errors += 1
                    continue

                _, ext = os.path.splitext(filename)
                if ext.lower() in REFACTOR_EXTENSIONS:
                    try:
                        text = content.decode("utf-8")
                        if old_word in text:
                            text    = text.replace(old_word, new_word)
                            content = text.encode("utf-8")
                    except (UnicodeDecodeError, ValueError):
                        pass

                relative_path = os.path.relpath(local_path, upload_from)
                git_path      = relative_path.replace(old_word, new_word).replace("\\", "/")

                try:
                    try:
                        existing = await asyncio.to_thread(repo.get_contents, git_path)
                        await asyncio.to_thread(
                            repo.update_file,
                            existing.path,
                            f"Refactor: {old_word} → {new_word}",
                            content,
                            existing.sha,
                        )
                    except GithubException:
                        await asyncio.to_thread(
                            repo.create_file,
                            git_path,
                            f"Upload: {git_path}",
                            content,
                        )
                    count += 1
                    await asyncio.sleep(0.3)
                except GithubException as exc:
                    print(f"[upload error] {git_path}: {exc}")
                    errors += 1

        # Clear pending data after successful upload
        await clear_pending(user_id)

        summary = (
            f"✅ **Repository successfully upgrade ho gayi!**\n\n"
            f"📦 **Repo:** `{repo_name}`\n"
            f"🔄 **Refactored:** `{old_word}` ➔ `{new_word}`\n"
            f"📄 **Files uploaded:** `{count}`\n"
        )
        if errors:
            summary += f"⚠️ **Skipped (errors):** `{errors}`\n"
        summary += f"\n🔗 **[GitHub pe dekho]({repo.html_url})**"

        await status.edit(summary, disable_web_page_preview=True)

    except Exception as exc:
        await status.edit(f"❌ **Error:** `{exc}`")

    finally:
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir)
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)


# ── Token commands ──────────────────────────────────────────────────────────

@app.on_message(filters.command("settoken"))
async def set_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database configured nahi hai.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/settoken <your_github_token>`")
    await tokens_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"token": message.command[1]}},
        upsert=True,
    )
    await message.delete()
    await message.reply_text("✅ GitHub token save ho gaya. Security ke liye aapka message delete kar diya.")


@app.on_message(filters.command("deltoken"))
async def del_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database configured nahi hai.")
    await tokens_col.delete_one({"user_id": message.from_user.id})
    await message.reply_text("🗑️ GitHub token delete ho gaya.")


__MODULE__ = "Upgrade"
__HELP__ = HELP_TEXT
