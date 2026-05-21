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

MAX_ZIP_MB = 50  # reject ZIPs larger than this

# --- DATABASE SETUP ---
tokens_col = None
if MONGO_DB_URL:
    mongo_client = AsyncIOMotorClient(MONGO_DB_URL)
    db = mongo_client["GitHubPublicBot"]
    tokens_col = db["user_tokens"]

# --- HELP TEXT ---
HELP_TEXT = """
🚀 **GITHUB REPO UPGRADER BOT**
━━━━━━━━━━━━━━━━━━━━━━
Upload and refactor repositories (replaces imports/folder names automatically).

🔐 **SETUP:**
• `/settoken <token>` — Save your GitHub Personal Access Token.
• `/deltoken` — Delete your saved token.

📤 **COMMANDS:**
• `/upload_repo <repo_name> <old_string> <new_string>`
• `/upgrade_repo <repo_name> <old_string> <new_string>`

**Example:**
`/upload_repo MyNewBot VIPMUSIC ALEX_MUSIC`
*(Replaces all occurrences of 'VIPMUSIC' with 'ALEX_MUSIC' before uploading)*
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


@app.on_message(filters.command(["upload_repo", "upgrade_repo"]))
async def upgrade_upload_handler(_, message: Message):
    user_id = message.from_user.id
    token = await get_token(user_id)

    if not token:
        return await message.reply_text(
            "🔑 **Please set your token first:** `/settoken <token>`"
        )

    if not (message.reply_to_message and message.reply_to_message.document):
        return await message.reply_text("❌ Please reply to a **.zip** file.")

    doc = message.reply_to_message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".zip"):
        return await message.reply_text("❌ The replied file must be a **.zip** archive.")

    if doc.file_size and doc.file_size > MAX_ZIP_MB * 1024 * 1024:
        return await message.reply_text(
            f"❌ ZIP is too large. Maximum allowed size is **{MAX_ZIP_MB} MB**."
        )

    if len(message.command) < 4:
        return await message.reply_text(
            "❌ **Invalid format.**\n\n"
            "Usage: `/upload_repo <repo_name> <word_to_find> <replacement>`\n"
            "Example: `/upload_repo MyBot VIPMUSIC NEW_BRAND`"
        )

    repo_name = message.command[1]
    old_word = message.command[2]
    new_word = message.command[3]

    status = await message.reply_text(
        f"⏳ **Initialising…**\n🔄 Will replace `{old_word}` → `{new_word}`"
    )

    extract_dir = f"work_{user_id}_{int(time.time())}"
    file_path: str | None = None

    try:
        # --- GitHub setup (blocking I/O → thread) ---
        g = await asyncio.to_thread(Github, token)
        user = await asyncio.to_thread(g.get_user)

        try:
            repo = await asyncio.to_thread(user.get_repo, repo_name)
        except GithubException:
            await status.edit(f"🔨 Creating repository `{repo_name}`…")
            repo = await asyncio.to_thread(
                user.create_repo, repo_name, auto_init=True
            )
            await asyncio.sleep(2)  # let GitHub initialise the default branch

        # --- Download & extract ---
        await status.edit("📥 **Downloading ZIP from Telegram…**")
        file_path = await message.reply_to_message.download()
        os.makedirs(extract_dir, exist_ok=True)
        _safe_extract(file_path, extract_dir)

        await status.edit("🚀 **Refactoring & uploading to GitHub…**")

        # If the ZIP contains a single top-level folder, use it as the root.
        entries = os.listdir(extract_dir)
        upload_from = (
            os.path.join(extract_dir, entries[0])
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0]))
            else extract_dir
        )

        count = 0
        errors = 0

        for root, _dirs, files in os.walk(upload_from):
            for filename in files:
                local_path = os.path.join(root, filename)

                # 1. Read file content
                try:
                    with open(local_path, "rb") as fh:
                        content = fh.read()
                except OSError as exc:
                    print(f"[read error] {local_path}: {exc}")
                    errors += 1
                    continue

                # 2. Replace text in supported file types
                _, ext = os.path.splitext(filename)
                if ext.lower() in REFACTOR_EXTENSIONS:
                    try:
                        text = content.decode("utf-8")
                        if old_word in text:
                            text = text.replace(old_word, new_word)
                            content = text.encode("utf-8")
                    except (UnicodeDecodeError, ValueError):
                        pass  # binary or non-UTF-8; upload as-is

                # 3. Rename paths
                relative_path = os.path.relpath(local_path, upload_from)
                git_path = relative_path.replace(old_word, new_word).replace("\\", "/")

                # 4. Upload (update if exists, create otherwise)
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
                    # Avoid GitHub secondary rate limits
                    await asyncio.sleep(0.3)
                except GithubException as exc:
                    print(f"[upload error] {git_path}: {exc}")
                    errors += 1

        summary = (
            f"✅ **Repository upgraded successfully!**\n\n"
            f"📦 **Repository:** `{repo_name}`\n"
            f"🔄 **Refactored:** `{old_word}` ➔ `{new_word}`\n"
            f"📄 **Files uploaded:** `{count}`\n"
        )
        if errors:
            summary += f"⚠️ **Skipped (errors):** `{errors}`\n"
        summary += f"\n🔗 **[View on GitHub]({repo.html_url})**"

        await status.edit(summary, disable_web_page_preview=True)

    except Exception as exc:
        await status.edit(f"❌ **Error:** `{exc}`")

    finally:
        # Always clean up — even if an exception was raised
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir)
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)


@app.on_message(filters.command("settoken"))
async def set_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database is not configured on this bot.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/settoken <your_github_token>`")
    await tokens_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"token": message.command[1]}},
        upsert=True,
    )
    await message.delete()  # remove the message so the token isn't visible in chat
    await message.reply_text("✅ GitHub token saved. Your message has been deleted for security.")


@app.on_message(filters.command("deltoken"))
async def del_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database is not configured on this bot.")
    await tokens_col.delete_one({"user_id": message.from_user.id})
    await message.reply_text("🗑️ GitHub token deleted.")


__MODULE__ = "Upgrade"
__HELP__ = HELP_TEXT
