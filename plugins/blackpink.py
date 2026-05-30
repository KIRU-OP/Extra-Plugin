from pyrogram import filters
from VIPMUSIC import app
from config import BANNED_USERS
import requests

@app.on_message(filters.command(["blackpink"]) & ~BANNED_USERS)
async def blackpink(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: /blackpink Name"
        )

    msg = await message.reply_text("Creating BlackPink Image...")

    name = " ".join(message.command[1:])

    url = f"https://api.popcat.xyz/textpro/blackpink?text={name}"

    try:
        await message.reply_photo(url)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

    await msg.delete()


__MODULE__ = "BLACKPINK"

__HELP__ = """
/blackpink [text]
Generate a BlackPink style logo image.
"""
