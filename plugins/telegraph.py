import os
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from VIPMUSIC import app


async def upload_to_telegraph(file_path: str) -> str:
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field(
                "file",
                f,
                filename=os.path.basename(file_path),
                content_type="image/jpeg",
            )
            async with session.post("https://telegra.ph/upload", data=data) as resp:
                result = await resp.json()
                if isinstance(result, list) and result and "src" in result[0]:
                    return "https://telegra.ph" + result[0]["src"]
                raise Exception(f"Telegraph response error: {result}")


async def upload_to_catbox(file_path: str) -> str:
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("reqtype", "fileupload")
            data.add_field("userhash", "")
            data.add_field(
                "fileToUpload",
                f,
                filename=os.path.basename(file_path),
            )
            async with session.post("https://catbox.moe/user/api.php", data=data) as resp:
                result = await resp.text()
                if result.startswith("https://"):
                    return result.strip()
                raise Exception(f"Catbox response error: {result}")


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Pʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ."
        )

    media = message.reply_to_message
    is_image = False

    if media.photo:
        is_image = True
    elif media.video:
        is_image = False
    elif media.animation:
        is_image = False
    elif media.document:
        mime = media.document.mime_type or ""
        if mime.startswith("image/"):
            is_image = True
    else:
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

        if is_image:
            await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ Tᴇʟᴇɢʀᴀᴘʜ...")
            upload_path = await upload_to_telegraph(local_path)
            host_name = "Tᴇʟᴇɢʀᴀᴘʜ"
            host_emoji = "📷"
        else:
            await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ Cᴀᴛʙᴏx...")
            upload_path = await upload_to_catbox(local_path)
            host_name = "Cᴀᴛʙᴏx"
            host_emoji = "🎥"

        await text.edit_text(
            f"✅ **Uᴘʟᴏᴀᴅᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
            f"{host_emoji} **Hᴏsᴛ:** {host_name}\n"
            f"🔗 **Lɪɴᴋ:** `{upload_path}`",
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
**ᴛᴇʟᴇɢʀᴀᴘʜ & ᴄᴀᴛʙᴏx ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴍᴀɴᴅs**

- `/tgm` — ᴍᴇᴅɪᴀ ᴜᴘʟᴏᴀᴅ ᴋᴀʀᴏ
- `/tgt` — sᴀᴍᴇ ᴀs `/tgm`
- `/telegraph` — sᴀᴍᴇ ᴀs `/tgm`
- `/tl` — sᴀᴍᴇ ᴀs `/tgm`

**ᴜᴘʟᴏᴀᴅ ʜᴏsᴛ:**
- 📷 **ɪᴍᴀɢᴇs** → Tᴇʟᴇɢʀᴀᴘʜ
- 🎥 **ᴠɪᴅᴇᴏs / ᴅᴏᴄs** → Cᴀᴛʙᴏx

**ɴᴏᴛᴇ:**
- ᴋɪsɪ ʙʜɪ ᴍᴇᴅɪᴀ ᴋᴏ ʀᴇᴘʟʏ ᴋᴀʀᴏ ᴄᴏᴍᴍᴀɴᴅ sᴇ
"""

__MODULE__ = "Tᴇʟᴇɢʀᴀᴘʜ"
