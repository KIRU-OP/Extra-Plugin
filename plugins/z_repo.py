import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

OWNERS = "-1003760069374"

from VIPMUSIC import app
from VIPMUSIC.utils.database import add_served_chat, get_assistant
from config import OWNER_ID


@app.on_message(filters.command("repo"))
async def repo_command(client: Client, message: Message):
    await message.reply_photo(
        photo="https://envs.sh/wWo.jpg",
        caption=(
            "🎵 ᴠɪᴘ ᴍᴜsɪᴄ — ᴏꜰꜰɪᴄɪᴀʟ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ\n\n"
            "🌟 ʜᴀᴍᴀʀᴀ ᴘᴏᴏʀᴀ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ ɢɪᴛʜᴜʙ ᴘᴀʀ ᴏᴘᴇɴʟʏ ᴀᴠᴀɪʟᴀʙʟᴇ ʜᴀɪ.\n"
            "🍴 ꜰᴏʀᴋ ᴋᴀʀᴋᴇ ᴀᴘɴᴀ ᴋʜᴜᴅ ᴋᴀ ᴘʀᴇᴍɪᴜᴍ ᴍᴜsɪᴄ ʙᴏᴛ ʙᴀɴᴀᴏ!\n\n"
            "🔐 ʟɪᴄᴇɴsᴇᴅ & ᴠᴇʀɪꜰɪᴇᴅ ʀᴇᴘᴏsɪᴛᴏʀʏ\n"
            "✦ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴀᴀʀᴜ ᴍᴜsɪᴄ ʙᴏᴛ"
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ sᴏᴜʀᴄᴇ ꜰᴏʀᴋ", url="https://github.com/KIRU-OP/VIP-MUSIC/fork"),
                InlineKeyboardButton("🔗 ᴠɪᴇᴡ ʀᴇᴘᴏ", url="https://github.com/KIRU-OP/VIP-MUSIC"),
            ]
        ]),
    )


@app.on_message(filters.command("clone"))
async def clone_command(client: Client, message: Message):
    await message.reply_photo(
        photo="https://envs.sh/wWo.jpg",
        caption=(
            "🚫 ᴘᴇʀᴍɪssɪᴏɴ ᴅᴇɴɪᴇᴅ\n\n"
            "😅 ʙʜᴀɪ ᴛᴜ sᴜᴅᴏ ᴜsᴇʀ ɴᴀʜɪ ʜᴀɪ, ɪsʟɪʏᴇ sᴇᴇᴅʜᴀ ᴄʟᴏɴᴇ ɴᴀʜɪ ᴋᴀʀ sᴀᴋᴛᴀ.\n\n"
            "💡 ᴋʏᴀ ᴋᴀʀᴇɴ?\n"
            "🍴 ɢɪᴛʜᴜʙ sᴇ ꜰᴏʀᴋ ᴋᴀʀᴋᴇ ᴋʜᴜᴅ ʜᴏsᴛ ᴋᴀʀᴏ.\n"
            "📩 ʏᴀ ᴏᴡɴᴇʀ / sᴜᴅᴏ ᴜsᴇʀs sᴇ ʀᴇǫᴜᴇsᴛ ᴋᴀʀᴏ ᴄʟᴏɴᴇ ᴋᴇ ʟɪʏᴇ.\n\n"
            "✦ ᴠɪᴘ ᴍᴜsɪᴄ — ᴏꜰꜰɪᴄɪᴀʟ"
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🍴 ꜰᴏʀᴋ & ʜᴏsᴛ", url="https:/github.com/KIRU-OP/VIP-MUSIC/fork"),
            ]
        ]),
    )


GREETING_TRIGGERS = ["hi", "hii", "hello", "hui", "good", "gm", "ok", "bye", "welcome", "thanks"]
GREETING_PREFIXES = ["/", "!", "%", ",", "", ".", "@", "#"]

@app.on_message(
    filters.command(GREETING_TRIGGERS, prefixes=GREETING_PREFIXES) & filters.group
)
async def track_served_chat(_, message: Message):
    await add_served_chat(message.chat.id)


EXCLUDED_CHAT = -1003760069374

@app.on_message(filters.command("gadd") & filters.user(OWNER_ID))
async def gadd_command(client: Client, message: Message):
    parts = message.text.split()

    if len(parts) != 2:
        await message.reply(
            "⚠️ ᴡʀᴏɴɢ ꜰᴏʀᴍᴀᴛ!\n\n"
            "📌 sᴀʜɪ ᴛᴀʀɪᴋᴀ:\n`/gadd @bot_username`"
        )
        return

    bot_username = parts[1]

    try:
        userbot = await get_assistant(message.chat.id)
        bot_user = await app.get_users(bot_username)
        bot_id = bot_user.id

        added = 0
        failed = 0

        status_msg = await message.reply(
            f"🚀 sᴛᴀʀᴛɪɴɢ ᴘʀᴏᴄᴇss...\n\n"
            f"🤖 ʙᴏᴛ: `{bot_username}`\n"
            f"⏳ sᴀᴀʀᴇ ᴄʜᴀᴛs ᴍᴇɪɴ ᴀᴅᴅ ʜᴏ ʀᴀʜᴀ ʜᴀɪ, ᴛʜᴏᴅᴀ ᴡᴀɪᴛ ᴋᴀʀᴏ..."
        )

        await userbot.send_message(bot_username, "/start")

        async for dialog in userbot.get_dialogs():
            if dialog.chat.id == EXCLUDED_CHAT:
                continue
            try:
                await userbot.add_chat_members(dialog.chat.id, bot_id)
                added += 1
            except Exception:
                failed += 1

            await status_msg.edit(
                f"🔄 ᴀᴅᴅɪɴɢ ɪɴ ᴘʀᴏɢʀᴇss...\n\n"
                f"🤖 ʙᴏᴛ: `{bot_username}`\n"
                f"✅ ᴀᴅᴅᴇᴅ: **{added}** ᴄʜᴀᴛs\n"
                f"❌ ꜰᴀɪʟᴇᴅ: **{failed}** ᴄʜᴀᴛs\n\n"
                f"👤 ᴜsᴇʀʙᴏᴛ: @{userbot.username}"
            )
            await asyncio.sleep(3)

        await status_msg.edit(
            f"🎉 sᴜᴄᴄᴇssꜰᴜʟʟʏ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!\n\n"
            f"🤖 ʙᴏᴛ: `{bot_username}`\n"
            f"✅ ᴀᴅᴅᴇᴅ: **{added}** ᴄʜᴀᴛs\n"
            f"❌ ꜰᴀɪʟᴇᴅ: **{failed}** ᴄʜᴀᴛs\n\n"
            f"👤 ʙʏ: @{userbot.username}"
        )

    except Exception as e:
        await message.reply(f"❗ ᴇʀʀᴏʀ: `{str(e)}`")


__MODULE__ = "sᴏᴜʀᴄᴇ"
__HELP__ = """
🎵 ᴠɪᴘ ᴍᴜsɪᴄ — ᴏꜰꜰɪᴄɪᴀʟ sᴏᴜʀᴄᴇ ᴍᴏᴅᴜʟᴇ

🌟 ʏᴇʜ ᴍᴏᴅᴜʟᴇ ʙᴏᴛ ᴋᴇ sᴏᴜʀᴄᴇ ᴀᴜʀ ᴜᴛɪʟɪᴛʏ ᴄᴏᴍᴍᴀɴᴅs ʜᴀɴᴅʟᴇ ᴋᴀʀᴛᴀ ʜᴀɪ.

📌 ᴄᴏᴍᴍᴀɴᴅs

🔗 /repo — ɢɪᴛʜᴜʙ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ ᴀᴜʀ ꜰᴏʀᴋ ʟɪɴᴋ ᴍɪʟᴇɢᴀ.

🍴 /clone — ᴍᴀɴᴜᴀʟʟʏ ʜᴏsᴛ ᴋᴀʀɴᴇ ᴋɪ ɪɴꜰᴏ ᴍɪʟᴇɢɪ (ɴᴏɴ-sᴜᴅᴏ ᴜsᴇʀs ᴋᴇ ʟɪʏᴇ).

🚀 /gadd @username — ᴅɪʏᴇ ʜᴜᴇ ʙᴏᴛ ᴋᴏ sᴀᴀʀᴇ ᴄʜᴀᴛs ᴍᴇɪɴ ᴀᴅᴅ ᴋᴀʀᴏ.
   👑 sɪʀꜰ ᴏᴡɴᴇʀ ᴋᴇ ʟɪʏᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ʜᴀɪ.

💬 ɢʀᴇᴇᴛɪɴɢs (ɢʀᴏᴜᴘ ᴍᴇɪɴ)
hi · hello · gm · bye · thanks · welcome
ᴛʏᴘᴇ ᴋᴀʀᴏ — ʙᴏᴛ sɪʟᴇɴᴛʟʏ ᴜs ɢʀᴏᴜᴘ ᴋᴏ sᴇʀᴠᴇ-ʟɪsᴛ ᴍᴇɪɴ ᴛʀᴀᴄᴋ ᴋᴀʀ ʟᴇᴛᴀ ʜᴀɪ.

✦ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴀᴀʀᴜ ᴍᴜsɪᴄ ʙᴏᴛ
"""
