import asyncio
import os
import shutil
import time
import zipfile
from datetime import datetime

from github import Github, GithubException
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from VIPMUSIC import app

# ─── CONFIG ────────────────────────────────────────────────────────────────────
try:
    try:
        from config import MONGO_DB_URI as MONGO_DB_URL
    except ImportError:
        from config import MONGO_DB_URL
except ImportError:
    MONGO_DB_URL = None

MAX_ZIP_MB = 50

# ─── DATABASE SETUP ────────────────────────────────────────────────────────────
tokens_col = None
if MONGO_DB_URL:
    mongo_client = AsyncIOMotorClient(MONGO_DB_URL)
    db = mongo_client["GitHubPublicBot"]
    tokens_col = db["user_tokens"]

# ─── CONSTANTS ─────────────────────────────────────────────────────────────────
REFACTOR_EXTENSIONS = {
    ".py", ".txt", ".md", ".yml", ".yaml",
    ".conf", ".env", ".json", ".toml", ".ini", ".sh", ".cfg",
}

# ─── HELP TEXT ─────────────────────────────────────────────────────────────────
HELP_TEXT = """
🚀 **GITHUB REPO MANAGER BOT**
━━━━━━━━━━━━━━━━━━━━━━

🔐 **TOKEN MANAGEMENT:**
• `/settoken <token>` — GitHub Personal Access Token save karo
• `/deltoken` — Token delete karo
• `/checktoken` — Token valid hai ya nahi check karo

📤 **UPLOAD & REFACTOR:**
• `/upload_repo <repo> <old> <new>` — ZIP se repo upload + refactor
• `/upgrade_repo <repo> <old> <new>` — Existing repo upgrade karo

📁 **REPOSITORY MANAGEMENT:**
• `/listrepos [page]` — Apni saari repos list karo
• `/repoinfo <repo>` — Repo ki detail info dekho
• `/createrepo <repo> [desc] [private]` — Naya repo banao
• `/deleterepo <repo>` — Repo delete karo (confirm karega)
• `/renamerepo <old_name> <new_name>` — Repo rename karo
• `/toggleprivate <repo>` — Public ↔ Private toggle karo

🌿 **BRANCH MANAGEMENT:**
• `/listbranches <repo>` — Saari branches dekho
• `/createbranch <repo> <branch> [from_branch]` — Naya branch banao
• `/deletebranch <repo> <branch>` — Branch delete karo
• `/defaultbranch <repo> <branch>` — Default branch change karo

📋 **FILE OPERATIONS:**
• `/listfiles <repo> [path] [branch]` — Repo ke files dekho
• `/readfile <repo> <path> [branch]` — File ka content padho
• `/deletefile <repo> <path> [branch]` — File delete karo

📜 **HISTORY & STATS:**
• `/commits <repo> [branch] [count]` — Commit history dekho
• `/repostats <repo>` — Stars, forks, issues stats
• `/searchrepo <query>` — Apne repos mein search karo

🔗 **TOPICS & SETTINGS:**
• `/addtopic <repo> <topic1> [topic2...]` — Topics add karo
• `/setdesc <repo> <description>` — Repo description update karo
• `/setwebsite <repo> <url>` — Website URL set karo

━━━━━━━━━━━━━━━━━━━━━━
"""

# ─── HELPERS ───────────────────────────────────────────────────────────────────

async def get_token(user_id: int) -> str | None:
    if not tokens_col:
        return None
    res = await tokens_col.find_one({"user_id": user_id})
    return res["token"] if res else None


async def get_github(user_id: int):
    """Returns (Github instance, user object) or raises if no token."""
    token = await get_token(user_id)
    if not token:
        raise ValueError("🔑 Pehle token set karo: `/settoken <token>`")
    g = await asyncio.to_thread(Github, token)
    user = await asyncio.to_thread(g.get_user)
    return g, user


def _safe_extract(zip_path: str, dest: str) -> None:
    dest = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            target = os.path.realpath(os.path.join(dest, member))
            if os.path.commonpath([dest, target]) != dest:
                raise ValueError(f"Unsafe ZIP path: {member}")
        zf.extractall(dest)


def fmt_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ─── TOKEN COMMANDS ────────────────────────────────────────────────────────────

@app.on_message(filters.command(["start", "help"]))
async def help_handler(_, message: Message):
    await message.reply_text(HELP_TEXT)


@app.on_message(filters.command("settoken"))
async def set_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database configure nahi hai.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/settoken <your_github_token>`")
    await tokens_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"token": message.command[1]}},
        upsert=True,
    )
    await message.delete()
    await message.reply_text("✅ Token save ho gaya. Message delete kar diya security ke liye.")


@app.on_message(filters.command("deltoken"))
async def del_token_cmd(_, message: Message):
    if not tokens_col:
        return await message.reply_text("❌ Database configure nahi hai.")
    await tokens_col.delete_one({"user_id": message.from_user.id})
    await message.reply_text("🗑️ GitHub token delete ho gaya.")


@app.on_message(filters.command("checktoken"))
async def check_token_cmd(_, message: Message):
    try:
        _, user = await get_github(message.from_user.id)
        login = await asyncio.to_thread(lambda: user.login)
        name = await asyncio.to_thread(lambda: user.name or "N/A")
        repos = await asyncio.to_thread(lambda: user.public_repos)
        await message.reply_text(
            f"✅ **Token Valid Hai!**\n\n"
            f"👤 **Username:** `{login}`\n"
            f"📛 **Name:** {name}\n"
            f"📦 **Public Repos:** {repos}"
        )
    except ValueError as e:
        await message.reply_text(str(e))
    except GithubException:
        await message.reply_text("❌ Token invalid ya expire ho gaya hai.")


# ─── UPLOAD / UPGRADE ──────────────────────────────────────────────────────────

@app.on_message(filters.command(["upload_repo", "upgrade_repo"]))
async def upgrade_upload_handler(_, message: Message):
    user_id = message.from_user.id
    try:
        _, user = await get_github(user_id)
    except ValueError as e:
        return await message.reply_text(str(e))

    if not (message.reply_to_message and message.reply_to_message.document):
        return await message.reply_text("❌ Ek **.zip** file reply karo command ke saath.")

    doc = message.reply_to_message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".zip"):
        return await message.reply_text("❌ File **.zip** honi chahiye.")

    if doc.file_size and doc.file_size > MAX_ZIP_MB * 1024 * 1024:
        return await message.reply_text(f"❌ ZIP bahut bada hai. Max **{MAX_ZIP_MB} MB** allowed.")

    if len(message.command) < 4:
        return await message.reply_text(
            "❌ **Format galat hai.**\n\n"
            "Usage: `/upload_repo <repo_name> <purana_word> <naya_word>`\n"
            "Example: `/upload_repo MyBot VIPMUSIC NEW_BRAND`"
        )

    repo_name, old_word, new_word = message.command[1], message.command[2], message.command[3]
    status = await message.reply_text(
        f"⏳ **Shuru ho raha hai…**\n🔄 `{old_word}` → `{new_word}` replace karunga"
    )

    extract_dir = f"work_{user_id}_{int(time.time())}"
    file_path: str | None = None

    try:
        try:
            repo = await asyncio.to_thread(user.get_repo, repo_name)
        except GithubException:
            await status.edit(f"🔨 Naya repo bana raha hoon: `{repo_name}`…")
            repo = await asyncio.to_thread(user.create_repo, repo_name, auto_init=True)
            await asyncio.sleep(2)

        await status.edit("📥 **Telegram se ZIP download ho raha hai…**")
        file_path = await message.reply_to_message.download()
        os.makedirs(extract_dir, exist_ok=True)
        _safe_extract(file_path, extract_dir)

        await status.edit("🚀 **Refactor + GitHub upload ho raha hai…**")

        entries = os.listdir(extract_dir)
        upload_from = (
            os.path.join(extract_dir, entries[0])
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0]))
            else extract_dir
        )

        count = errors = 0

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
                            content = text.replace(old_word, new_word).encode("utf-8")
                    except (UnicodeDecodeError, ValueError):
                        pass

                relative_path = os.path.relpath(local_path, upload_from)
                git_path = relative_path.replace(old_word, new_word).replace("\\", "/")

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
                            repo.create_file, git_path, f"Upload: {git_path}", content
                        )
                    count += 1
                    await asyncio.sleep(0.3)
                except GithubException as exc:
                    print(f"[upload error] {git_path}: {exc}")
                    errors += 1

        summary = (
            f"✅ **Repo successfully upgrade ho gaya!**\n\n"
            f"📦 **Repo:** `{repo_name}`\n"
            f"🔄 **Refactored:** `{old_word}` ➔ `{new_word}`\n"
            f"📄 **Files uploaded:** `{count}`\n"
        )
        if errors:
            summary += f"⚠️ **Skip (errors):** `{errors}`\n"
        summary += f"\n🔗 **[GitHub pe dekho]({repo.html_url})**"
        await status.edit(summary, disable_web_page_preview=True)

    except Exception as exc:
        await status.edit(f"❌ **Error:** `{exc}`")
    finally:
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir)
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)


# ─── REPOSITORY LISTING ────────────────────────────────────────────────────────

@app.on_message(filters.command("listrepos"))
async def list_repos_cmd(_, message: Message):
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    page = int(message.command[1]) if len(message.command) > 1 else 1
    per_page = 10
    status = await message.reply_text("🔍 Repos fetch ho rahi hain…")

    try:
        repos = await asyncio.to_thread(lambda: list(user.get_repos(sort="updated")))
        total = len(repos)
        start = (page - 1) * per_page
        end = start + per_page
        page_repos = repos[start:end]

        if not page_repos:
            return await status.edit("❌ Is page pe koi repo nahi mili.")

        text = f"📁 **Tumhari Repos** (Page {page}/{(total + per_page - 1) // per_page})\n"
        text += f"📊 **Total:** {total} repos\n\n"

        for i, repo in enumerate(page_repos, start + 1):
            visibility = "🔒" if repo.private else "🌐"
            lang = repo.language or "Unknown"
            stars = repo.stargazers_count
            text += f"{i}. {visibility} **{repo.name}** — ⭐{stars} | `{lang}`\n"

        if end < total:
            text += f"\n➡️ Agle ke liye: `/listrepos {page + 1}`"

        await status.edit(text)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc}`")


# ─── REPO INFO ─────────────────────────────────────────────────────────────────

@app.on_message(filters.command("repoinfo"))
async def repo_info_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/repoinfo <repo_name>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    status = await message.reply_text("🔍 Info fetch ho rahi hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, message.command[1])
        created = repo.created_at.strftime("%d %b %Y")
        updated = repo.updated_at.strftime("%d %b %Y")
        visibility = "🔒 Private" if repo.private else "🌐 Public"
        lang = repo.language or "N/A"
        topics = ", ".join(repo.get_topics()) or "None"
        size = fmt_size(repo.size * 1024)

        text = (
            f"📦 **{repo.name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **Desc:** {repo.description or 'N/A'}\n"
            f"🔐 **Visibility:** {visibility}\n"
            f"💻 **Language:** {lang}\n"
            f"⭐ **Stars:** {repo.stargazers_count}\n"
            f"🍴 **Forks:** {repo.forks_count}\n"
            f"👁️ **Watchers:** {repo.watchers_count}\n"
            f"🐛 **Open Issues:** {repo.open_issues_count}\n"
            f"📏 **Size:** {size}\n"
            f"🌿 **Default Branch:** {repo.default_branch}\n"
            f"🏷️ **Topics:** {topics}\n"
            f"📅 **Created:** {created}\n"
            f"🔄 **Updated:** {updated}\n"
            f"🔗 [GitHub pe dekho]({repo.html_url})"
        )
        await status.edit(text, disable_web_page_preview=True)
    except GithubException:
        await status.edit(f"❌ Repo `{message.command[1]}` nahi mili.")


# ─── CREATE REPO ───────────────────────────────────────────────────────────────

@app.on_message(filters.command("createrepo"))
async def create_repo_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: `/createrepo <name> [description] [private]`\n"
            "Example: `/createrepo MyBot 'My cool bot' private`"
        )
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    parts = message.command
    repo_name = parts[1]
    description = parts[2] if len(parts) > 2 else ""
    is_private = len(parts) > 3 and parts[3].lower() == "private"

    status = await message.reply_text(f"🔨 Repo `{repo_name}` ban raha hai…")
    try:
        repo = await asyncio.to_thread(
            user.create_repo,
            repo_name,
            description=description,
            private=is_private,
            auto_init=True,
        )
        visibility = "🔒 Private" if is_private else "🌐 Public"
        await status.edit(
            f"✅ **Repo successfully bana!**\n\n"
            f"📦 **Name:** `{repo.name}`\n"
            f"🔐 **Visibility:** {visibility}\n"
            f"🔗 [Dekho]({repo.html_url})",
            disable_web_page_preview=True,
        )
    except GithubException as exc:
        await status.edit(f"❌ Repo nahi bana: `{exc.data.get('message', exc)}`")


# ─── DELETE REPO ───────────────────────────────────────────────────────────────

# Pending deletes stored in-memory (user_id -> repo_name)
_pending_deletes: dict[int, str] = {}


@app.on_message(filters.command("deleterepo"))
async def delete_repo_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/deleterepo <repo_name>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    try:
        await asyncio.to_thread(user.get_repo, repo_name)
    except GithubException:
        return await message.reply_text(f"❌ Repo `{repo_name}` nahi mili.")

    _pending_deletes[message.from_user.id] = repo_name
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Haan, Delete Karo", callback_data=f"confirm_del_{message.from_user.id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_del_{message.from_user.id}"),
        ]
    ])
    await message.reply_text(
        f"⚠️ **Kya tum sach mein `{repo_name}` delete karna chahte ho?**\n\n"
        "Yeh action **irreversible** hai!",
        reply_markup=keyboard,
    )


@app.on_callback_query(filters.regex(r"^(confirm|cancel)_del_(\d+)$"))
async def delete_confirm_callback(_, callback: CallbackQuery):
    action, uid = callback.data.split("_del_")
    uid = int(uid)

    if callback.from_user.id != uid:
        return await callback.answer("Yeh tumhara button nahi hai!", show_alert=True)

    repo_name = _pending_deletes.pop(uid, None)
    if not repo_name:
        return await callback.message.edit_text("⚠️ Request expire ho gayi. Dobara try karo.")

    if action == "cancel":
        return await callback.message.edit_text("❌ Delete cancel ho gaya.")

    try:
        _, user = await get_github(uid)
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        await asyncio.to_thread(repo.delete)
        await callback.message.edit_text(f"🗑️ Repo `{repo_name}` delete ho gaya.")
    except Exception as exc:
        await callback.message.edit_text(f"❌ Delete nahi hua: `{exc}`")


# ─── RENAME REPO ───────────────────────────────────────────────────────────────

@app.on_message(filters.command("renamerepo"))
async def rename_repo_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/renamerepo <purana_naam> <naya_naam>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    old_name, new_name = message.command[1], message.command[2]
    status = await message.reply_text(f"✏️ Rename ho raha hai `{old_name}` → `{new_name}`…")
    try:
        repo = await asyncio.to_thread(user.get_repo, old_name)
        await asyncio.to_thread(repo.edit, name=new_name)
        await status.edit(
            f"✅ Repo rename ho gaya!\n\n"
            f"📦 **Naya naam:** `{new_name}`\n"
            f"🔗 [Dekho](https://github.com/{user.login}/{new_name})",
            disable_web_page_preview=True,
        )
    except GithubException as exc:
        await status.edit(f"❌ Rename nahi hua: `{exc.data.get('message', exc)}`")


# ─── TOGGLE PRIVATE/PUBLIC ─────────────────────────────────────────────────────

@app.on_message(filters.command("toggleprivate"))
async def toggle_private_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/toggleprivate <repo_name>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    status = await message.reply_text("🔄 Visibility change ho rahi hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, message.command[1])
        new_private = not repo.private
        await asyncio.to_thread(repo.edit, private=new_private)
        vis = "🔒 Private" if new_private else "🌐 Public"
        await status.edit(f"✅ `{repo.name}` ab **{vis}** hai!")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── BRANCH MANAGEMENT ─────────────────────────────────────────────────────────

@app.on_message(filters.command("listbranches"))
async def list_branches_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/listbranches <repo_name>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    status = await message.reply_text("🔍 Branches fetch ho rahi hain…")
    try:
        repo = await asyncio.to_thread(user.get_repo, message.command[1])
        branches = await asyncio.to_thread(lambda: list(repo.get_branches()))
        default = repo.default_branch

        text = f"🌿 **{repo.name} ke Branches** ({len(branches)} total)\n\n"
        for b in branches:
            marker = " ← default" if b.name == default else ""
            protected = " 🔒" if b.protected else ""
            text += f"• `{b.name}`{protected}{marker}\n"

        await status.edit(text)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc}`")


@app.on_message(filters.command("createbranch"))
async def create_branch_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "Usage: `/createbranch <repo> <naya_branch> [se_branch]`\n"
            "Example: `/createbranch MyBot feature-x main`"
        )
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    new_branch = message.command[2]
    from_branch = message.command[3] if len(message.command) > 3 else None

    status = await message.reply_text(f"🌿 Branch `{new_branch}` ban raha hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        source = from_branch or repo.default_branch
        source_branch = await asyncio.to_thread(repo.get_branch, source)
        sha = source_branch.commit.sha
        await asyncio.to_thread(repo.create_git_ref, f"refs/heads/{new_branch}", sha)
        await status.edit(
            f"✅ Branch bana diya!\n\n"
            f"🌿 **`{new_branch}`** from **`{source}`**"
        )
    except GithubException as exc:
        await status.edit(f"❌ Branch nahi bana: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("deletebranch"))
async def delete_branch_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/deletebranch <repo> <branch>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name, branch_name = message.command[1], message.command[2]
    status = await message.reply_text(f"🗑️ Branch `{branch_name}` delete ho raha hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        ref = await asyncio.to_thread(repo.get_git_ref, f"heads/{branch_name}")
        await asyncio.to_thread(ref.delete)
        await status.edit(f"✅ Branch `{branch_name}` delete ho gaya!")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("defaultbranch"))
async def default_branch_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/defaultbranch <repo> <branch>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    status = await message.reply_text("🔄 Default branch change ho raha hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, message.command[1])
        await asyncio.to_thread(repo.edit, default_branch=message.command[2])
        await status.edit(f"✅ Default branch ab `{message.command[2]}` hai!")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── FILE OPERATIONS ───────────────────────────────────────────────────────────

@app.on_message(filters.command("listfiles"))
async def list_files_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: `/listfiles <repo> [path] [branch]`\n"
            "Example: `/listfiles MyBot src main`"
        )
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    path = message.command[2] if len(message.command) > 2 else ""
    branch = message.command[3] if len(message.command) > 3 else None

    status = await message.reply_text("🔍 Files fetch ho rahi hain…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        kwargs = {"path": path}
        if branch:
            kwargs["ref"] = branch
        contents = await asyncio.to_thread(lambda: repo.get_contents(**kwargs))
        if not isinstance(contents, list):
            contents = [contents]

        dirs = sorted([c for c in contents if c.type == "dir"], key=lambda x: x.name)
        files = sorted([c for c in contents if c.type == "file"], key=lambda x: x.name)

        folder = path or "/"
        text = f"📁 **{repo_name}/{folder}**\n\n"

        for d in dirs:
            text += f"📂 `{d.name}/`\n"
        for f in files:
            size = fmt_size(f.size)
            text += f"📄 `{f.name}` ({size})\n"

        text += f"\n📊 **{len(dirs)} folder, {len(files)} file**"
        await status.edit(text)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("readfile"))
async def read_file_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "Usage: `/readfile <repo> <path> [branch]`\n"
            "Example: `/readfile MyBot README.md`"
        )
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name, file_path = message.command[1], message.command[2]
    branch = message.command[3] if len(message.command) > 3 else None

    status = await message.reply_text("📖 File padha ja raha hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        kwargs = {"path": file_path}
        if branch:
            kwargs["ref"] = branch
        content_file = await asyncio.to_thread(lambda: repo.get_contents(**kwargs))
        decoded = content_file.decoded_content.decode("utf-8", errors="replace")

        MAX_LEN = 3800
        if len(decoded) > MAX_LEN:
            decoded = decoded[:MAX_LEN] + "\n\n… (file bahut badi hai, truncate kar diya)"

        await status.edit(
            f"📄 **{file_path}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"```\n{decoded}\n```"
        )
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("deletefile"))
async def delete_file_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/deletefile <repo> <path> [branch]`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name, file_path = message.command[1], message.command[2]
    branch = message.command[3] if len(message.command) > 3 else None

    status = await message.reply_text(f"🗑️ File `{file_path}` delete ho rahi hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        kwargs = {"path": file_path}
        if branch:
            kwargs["ref"] = branch
        f = await asyncio.to_thread(lambda: repo.get_contents(**kwargs))
        delete_kwargs = {"path": f.path, "message": f"Delete: {file_path}", "sha": f.sha}
        if branch:
            delete_kwargs["branch"] = branch
        await asyncio.to_thread(lambda: repo.delete_file(**delete_kwargs))
        await status.edit(f"✅ File `{file_path}` delete ho gayi!")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── COMMIT HISTORY ────────────────────────────────────────────────────────────

@app.on_message(filters.command("commits"))
async def commits_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: `/commits <repo> [branch] [count]`\n"
            "Example: `/commits MyBot main 5`"
        )
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    branch = message.command[2] if len(message.command) > 2 else None
    count = int(message.command[3]) if len(message.command) > 3 else 5
    count = min(count, 20)  # max 20 commits

    status = await message.reply_text("📜 Commits fetch ho rahe hain…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        kwargs = {}
        if branch:
            kwargs["sha"] = branch
        commits = await asyncio.to_thread(lambda: list(repo.get_commits(**kwargs)[:count]))

        b_label = branch or repo.default_branch
        text = f"📜 **{repo_name} ({b_label}) — Last {len(commits)} Commits**\n\n"

        for commit in commits:
            msg = commit.commit.message.split("\n")[0][:60]
            author = commit.commit.author.name
            date = commit.commit.author.date.strftime("%d %b")
            sha = commit.sha[:7]
            text += f"🔹 `{sha}` **{msg}**\n   👤 {author} | 📅 {date}\n\n"

        await status.edit(text)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── REPO STATS ────────────────────────────────────────────────────────────────

@app.on_message(filters.command("repostats"))
async def repo_stats_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/repostats <repo_name>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    status = await message.reply_text("📊 Stats fetch ho rahi hain…")
    try:
        repo = await asyncio.to_thread(user.get_repo, message.command[1])
        branches = await asyncio.to_thread(lambda: repo.get_branches().totalCount)
        tags = await asyncio.to_thread(lambda: repo.get_tags().totalCount)
        contributors = await asyncio.to_thread(lambda: repo.get_contributors().totalCount)

        text = (
            f"📊 **{repo.name} — Statistics**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ Stars: **{repo.stargazers_count}**\n"
            f"🍴 Forks: **{repo.forks_count}**\n"
            f"👁️ Watchers: **{repo.watchers_count}**\n"
            f"🐛 Open Issues: **{repo.open_issues_count}**\n"
            f"🌿 Branches: **{branches}**\n"
            f"🏷️ Tags: **{tags}**\n"
            f"👥 Contributors: **{contributors}**\n"
            f"💻 Language: **{repo.language or 'N/A'}**\n"
            f"📏 Size: **{fmt_size(repo.size * 1024)}**\n"
            f"🔗 [GitHub pe dekho]({repo.html_url})"
        )
        await status.edit(text, disable_web_page_preview=True)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── SEARCH REPOS ──────────────────────────────────────────────────────────────

@app.on_message(filters.command("searchrepo"))
async def search_repo_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/searchrepo <query>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    query = " ".join(message.command[1:]).lower()
    status = await message.reply_text(f"🔍 `{query}` dhundh raha hoon…")
    try:
        repos = await asyncio.to_thread(lambda: list(user.get_repos()))
        matches = [r for r in repos if query in r.name.lower() or (r.description and query in r.description.lower())]

        if not matches:
            return await status.edit(f"❌ `{query}` se koi repo nahi mili.")

        text = f"🔍 **Search: `{query}`** — {len(matches)} result(s)\n\n"
        for repo in matches[:15]:
            vis = "🔒" if repo.private else "🌐"
            text += f"{vis} **{repo.name}** — ⭐{repo.stargazers_count}\n"

        await status.edit(text)
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc}`")


# ─── TOPICS & SETTINGS ─────────────────────────────────────────────────────────

@app.on_message(filters.command("addtopic"))
async def add_topic_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/addtopic <repo> <topic1> [topic2...]`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    new_topics = [t.lower() for t in message.command[2:]]

    status = await message.reply_text("🏷️ Topics add ho rahe hain…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        existing = await asyncio.to_thread(repo.get_topics)
        combined = list(set(existing + new_topics))
        await asyncio.to_thread(repo.replace_topics, combined)
        await status.edit(
            f"✅ Topics add ho gaye!\n\n"
            f"🏷️ **Topics:** {', '.join(f'`{t}`' for t in combined)}"
        )
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("setdesc"))
async def set_desc_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/setdesc <repo> <description>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name = message.command[1]
    desc = " ".join(message.command[2:])
    status = await message.reply_text("✏️ Description update ho rahi hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        await asyncio.to_thread(repo.edit, description=desc)
        await status.edit(f"✅ Description update ho gayi!\n\n📝 `{desc}`")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


@app.on_message(filters.command("setwebsite"))
async def set_website_cmd(_, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/setwebsite <repo> <url>`")
    try:
        _, user = await get_github(message.from_user.id)
    except ValueError as e:
        return await message.reply_text(str(e))

    repo_name, url = message.command[1], message.command[2]
    status = await message.reply_text("🔗 Website URL set ho raha hai…")
    try:
        repo = await asyncio.to_thread(user.get_repo, repo_name)
        await asyncio.to_thread(repo.edit, homepage=url)
        await status.edit(f"✅ Website URL set ho gayi!\n\n🔗 `{url}`")
    except GithubException as exc:
        await status.edit(f"❌ Error: `{exc.data.get('message', exc)}`")


# ─── MODULE META ───────────────────────────────────────────────────────────────
__MODULE__ = "upgrade"
__HELP__ = HELP_TEXT
