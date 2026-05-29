import os
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from VIPMUSIC import app
from telegraph import Telegraph

api = Telegraph()
api.create_account(short_name="VIPMusic")

async def upload_to_catbox(file_path: str) -> str:
    """Upload any file to catbox.moe and return the URL."""
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("reqtype", "fileupload")
            form.add_field("userhash", "")  # anonymous upload
            form.add_field("fileToUpload", f, filename=os.path.basename(file_path))
            async with session.post("https://catbox.moe/user/api.php", data=form) as resp:
                result = await resp.text()
                if result.startswith("https://"):
                    return result.strip()
                raise Exception(f"Catbox error: {result}")


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Pʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ."
        )

    media = message.reply_to_message
    file_size = 0
    is_image = False
    use_catbox = False

    if media.photo:
        file_size = media.photo.file_size
        is_image = True
    elif media.video:
        file_size = media.video.file_size
        use_catbox = True
    elif media.animation:
        file_size = media.animation.file_size
        use_catbox = True
    elif media.document:
        file_size = media.document.file_size
        mime = media.document.mime_type or ""
        if mime.startswith("image/"):
            is_image = True
        elif mime.startswith("video/"):
            use_catbox = True
        else:
            use_catbox = True  # allow all document types via catbox
    else:
        return await message.reply_text(
            "❌ Pʜᴏᴛᴏ, ᴠɪᴅᴇᴏ, ᴏʀ ᴅᴏᴄᴜᴍᴇɴᴛ ʀᴇᴘʟʏ ᴋᴀʀᴏ."
        )

    # Telegraph limit: 15MB | Catbox limit: 200MB
    max_size = 200 * 1024 * 1024 if use_catbox else 15 * 1024 * 1024
    size_label = "200MB" if use_catbox else "15MB"

    if file_size > max_size:
        return await message.reply_text(
            f"❌ Fɪʟᴇ ᴛᴏᴏ ʟᴀʀɢᴇ! Mᴀx sɪᴢᴇ: **{size_label}**"
        )

    local_path = None
    text = None
    try:
        text = await message.reply("⏳ Pʀᴏᴄᴇssɪɴɢ...")

        async def progress(current, total):
            try:
                await text.edit_text(f"📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ... {current * 100 / total:.1f}%")
            except Exception:
                pass

        local_path = await media.download(progress=progress)

        if is_image:
            await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ Tᴇʟᴇɢʀᴀᴘʜ...")
            upload_path = api.upload_image(local_path)
            if isinstance(upload_path, list):
                upload_path = upload_path[0]
            if not upload_path.startswith("http"):
                upload_path = "https://telegra.ph" + upload_path
            host_name = "Tᴇʟᴇɢʀᴀᴘʜ"

        elif use_catbox:
            await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ ᴛᴏ Cᴀᴛʙᴏx...")
            upload_path = await upload_to_catbox(local_path)
            host_name = "Cᴀᴛʙᴏx"

        await text.edit_text(
            f"✅ **Uᴘʟᴏᴀᴅᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
            f"🌐 **Hᴏsᴛ:** {host_name}\n"
            f"🔗 **Lɪɴᴋ:** {upload_path}",
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
- 🖼 **ɪᴍᴀɢᴇs** → Tᴇʟᴇɢʀᴀᴘʜ (ᴍᴀx 15MB)
- 🎥 **ᴠɪᴅᴇᴏs / ᴅᴏᴄs** → Cᴀᴛʙᴏx (ᴍᴀx 200MB)

**ᴇxᴀᴍᴘʟᴇ:**
ᴋɪsɪ ʙʜɪ ᴍᴇᴅɪᴀ ᴋᴏ ʀᴇᴘʟʏ ᴋᴀʀᴏ `/tgm` sᴇ.
"""

__MODULE__ = "Tᴇʟᴇɢʀᴀᴘʜ"
