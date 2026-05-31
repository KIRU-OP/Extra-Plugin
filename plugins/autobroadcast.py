import asyncio
import datetime
import pytz
from time import time
from typing import Optional, Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import AUTO_GCAST, AUTO_GCAST_MSG, LOG_GROUP_ID
from VIPMUSIC import app
from VIPMUSIC.utils.database import get_served_chats

# Convert AUTO_GCAST to boolean
AUTO_GCASTS = AUTO_GCAST.strip().lower() == "on"

# Image and Messages
START_IMG_URLS = "https://envs.sh/BjZ.jpg"

MESSAGE = """**
๏ ᴛʜɪs ɪs ᴀᴅᴠᴀɴᴄᴇᴅ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘs + ᴄʜᴀɴɴᴇʟs ᴠᴄ. 💌

🎧 ᴘʟᴀʏ + ᴠᴘʟᴀʏ + ᴄᴘʟᴀʏ 🎧

➥ sᴜᴘᴘᴏʀᴛᴇᴅ ᴡᴇʟᴄᴏᴍᴇ - ʟᴇғᴛ ɴᴏᴛɪᴄᴇ, ᴛᴀɢᴀʟʟ, ᴠᴄᴛᴀɢ, ʙᴀɴ - ᴍᴜᴛᴇ, sʜᴀʏʀɪ, ʟʏʀɪᴄs, sᴏɴɢ - ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅ, ᴇᴛᴄ... ❤️

🔐ᴜꜱᴇ » [/start](https://t.me/aaru_music_rbot?start=help) ᴛᴏ ᴄʜᴇᴄᴋ ʙᴏᴛ

➲ ʙᴏᴛ :**[ᴀᴀʀᴜ ꭙ ᴍᴜsɪᴄ ♡゙](https://t.me/aaru_music_rbot?start=help)"""

BUTTON = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "๏ ᴀᴅᴅ ᴍᴇ ๏",
                url=f"https://t.me/aaru_music_rbot?startgroup=s&admin=delete_messages+manage_video_chats+pin_messages+invite_users",
            )
        ]
    ]
)

caption = f"""{AUTO_GCAST_MSG}""" if AUTO_GCAST_MSG else MESSAGE

TEXT = """**ᴀᴜᴛᴏ ɢᴄᴀsᴛ ɪs ᴇɴᴀʙʟᴇᴅ sᴏ ᴀᴜᴛᴏ ɢᴄᴀsᴛ/ʙʀᴏᴀᴅᴄᴀsᴛ ɪs ᴅᴏɪɴɢ ɪɴ ᴀʟʟ ᴄʜᴀᴛs ᴏɴ sᴄʜᴇᴅᴜʟᴇᴅ ᴛɪᴍᴇ.**\n**ɪᴛ ᴄᴀɴ ʙᴇ sᴛᴏᴘᴘᴇᴅ ʙʏ ᴘᴜᴛ ᴠᴀʀɪᴀʙʟᴇ [ᴀᴜᴛᴏ_ɢᴄᴀsᴛ = (Off)]**"""

# Scheduled Times in 24-hour format (Indian Time)
# Har 5 ghante mein - 00:00, 05:00, 10:00, 15:00, 20:00
SCHEDULED_TIMES = ["00:00", "05:00", "10:00", "15:00", "20:00"]

# Timezone set to India
IST = pytz.timezone('Asia/Kolkata')


async def send_text_once():
    try:
        await app.send_message(LOG_GROUP_ID, TEXT)
    except Exception:
        pass


async def send_message_to_chats():
    try:
        chats = await get_served_chats()
        for chat_info in chats:
            chat_id = chat_info.get("chat_id")
            if isinstance(chat_id, int):
                try:
                    await app.send_photo(
                        chat_id,
                        photo=START_IMG_URLS,
                        caption=caption,
                        reply_markup=BUTTON,
                    )
                    # Har message ke baad 3 second ka gap taaki bot spam mein na aaye
                    await asyncio.sleep(3)
                except Exception:
                    pass
    except Exception:
        pass


async def continuous_broadcast():
    # Bot start hone par ek baar log group mein message bhejega
    await send_text_once()

    while True:
        if AUTO_GCASTS:
            # India ka current time check karein
            now_ist = datetime.datetime.now(IST)
            current_time = now_ist.strftime("%H:%M")

            if current_time in SCHEDULED_TIMES:
                try:
                    await send_message_to_chats()
                except Exception:
                    pass

                # Ek minute ka sleep taaki ussi minute mein dobara broadcast na ho
                await asyncio.sleep(60)

        # Har 30 seconds mein check karega ki time hua ya nahi
        await asyncio.sleep(30)


# Start the task
if AUTO_GCASTS:
    asyncio.create_task(continuous_broadcast())
