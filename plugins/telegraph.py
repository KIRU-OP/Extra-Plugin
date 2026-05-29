import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from VIPMUSIC import app
from VIPMUSIC.core.userbot import assistants  # ya jo bhi tumhara userbot import hai


# Apna ek PUBLIC channel banao aur uska ID yahan daalo
STORAGE_CHANNEL = -1003884346368  # 👈 Apne channel ka ID daalo


async def upload_to_telegram(file_path: str, caption: str = "") -> str:
    """File ko storage channel mein bhejo aur direct link lo"""
    # Bot se channel mein file bhejo
    if file_path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        msg = await app.send_photo(
            STORAGE_CHANNEL,
            file_path,
            caption=caption,
        )
        file_id = msg.photo.file_id
    elif file_path.endswith((".mp4", ".mkv", ".avi", ".mov")):
        msg = await app.send_video(
            STORAGE_CHANNEL,
            file_path,
            caption=caption,
            supports_streaming=True,
        )
        file_id = msg.video.file_id
    else:
        msg = await app.send_document(
            STORAGE_CHANNEL,
            file_path,
            caption=caption,
        )
        file_id = msg.document.file_id

    # Message ka direct link banao
    # Channel username ho toh: https://t.me/username/msg_id
    # Private channel ho toh: https://t.me/c/channel_id/msg_id
    channel_id = str(STORAGE_CHANNEL)
    if channel_id.startswith("-100"):
        channel_id = channel_id[4:]  # -100 hatao
    link = f"https://t.me/c/{channel_id}/{msg.id}"
    return link, file_id


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Pʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ."
        )

    media = message.reply_to_message

    if not (media.photo or media.video or media.document or media.animation or media.audio or media.voice or media.video_note):
        return await message.reply_text(
            "❌ Pʜᴏᴛᴏ, ᴠɪᴅᴇᴏ, ᴏʀ ᴅᴏᴄᴜᴍᴇɴᴛ ʀᴇᴘʟʏ ᴋᴀʀᴏ."
        )

    local_path = None
    text = None

    try:
        text = await message.reply("⏳ Pʀᴏᴄᴇssɪɴɢ...")

        async def progress(current, total):
            try:
                await text.edit_text(
                    f"📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ... {current * 100 / total:.1f}%"
                )
            except Exception:
                pass

        local_path = await media.download(progress=progress)
        await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ Tᴇʟᴇɢʀᴀᴍ...")

        upload_path, file_id = await upload_to_telegram(
            local_path,
            caption=f"Uᴘʟᴏᴀᴅᴇᴅ ʙʏ @{message.from_user.username or message.from_user.id}"
        )

        await text.edit_text(
            f"✅ **Uᴘʟᴏᴀᴅᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
            f"📦 **Hᴏsᴛ:** Tᴇʟᴇɢʀᴀᴍ\n"
            f"🔗 **Lɪɴᴋ:** `{upload_path}`\n"
            f"🆔 **Fɪʟᴇ ID:** `{file_id}`",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🌐 Oᴘᴇɴ Lɪɴᴋ",
                            url=upload_path,
                        )
                    ]
                ]
            ),
        )

    except Exception as e:
        if text:
            await text.edit_text(
                f"❌ **Fɪʟᴇ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ**\n\n<i>Rᴇᴀsᴏɴ: {e}</i>"
            )
    finally:
        if local_path:
            try:
                os.remove(local_path)
            except Exception:
                pass


__HELP__ = """
**ᴛᴇʟᴇɢʀᴀᴍ sᴇʟғ-ʜᴏsᴛɪɴɢ ᴜᴘʟᴏᴀᴅ**

- `/tgm` — ᴍᴇᴅɪᴀ ᴜᴘʟᴏᴀᴅ ᴋᴀʀᴏ
- `/tgt` — sᴀᴍᴇ ᴀs `/tgm`
- `/telegraph` — sᴀᴍᴇ ᴀs `/tgm`
- `/tl` — sᴀᴍᴇ ᴀs `/tgm`

**ᴋᴀɪsᴇ ᴋᴀᴍ ᴋᴀʀᴛᴀ ʜᴀɪ:**
ᴍᴇᴅɪᴀ ᴅɪʀᴇᴄᴛ Tᴇʟᴇɢʀᴀᴍ sᴛᴏʀᴀɢᴇ ᴄʜᴀɴɴᴇʟ ᴍᴇɪɴ sᴀᴠᴇ ʜᴏᴛɪ ʜᴀɪ.
ᴋᴏɪ ᴇxᴛᴇʀɴᴀʟ sᴇʀᴠɪᴄᴇ ɴᴀʜɪɴ, sʙ Tᴇʟᴇɢʀᴀᴍ ᴘᴇ!

**ɴᴏᴛᴇ:**
- ᴋɪsɪ ʙʜɪ ᴍᴇᴅɪᴀ ᴋᴏ ʀᴇᴘʟʏ ᴋᴀʀᴏ ᴄᴏᴍᴍᴀɴᴅ sᴇ
- Fɪʟᴇ ʜᴀᴍᴇsʜᴀ ᴀᴠᴀɪʟᴀʙʟᴇ ʀʜᴇɢɪ
"""

__MODULE__ = "Tᴇʟᴇɢʀᴀᴘʜ"
