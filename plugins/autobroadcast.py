import asyncio
import datetime
import pytz
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import AUTO_GCAST, AUTO_GCAST_MSG, LOG_GROUP_ID
from VIPMUSIC import app
from VIPMUSIC.utils.database import get_served_chats

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_GCASTS: bool = AUTO_GCAST.strip().lower() == "on"
IST = pytz.timezone("Asia/Kolkata")

# Har 5 ghante mein broadcast — 24 ghante mein 4-5 baar (IST)
# 00:00 → 05:00 → 10:00 → 15:00 → 20:00
SCHEDULED_TIMES = ["00:00", "05:00", "10:00", "15:00", "20:00"]

# ═══════════════════════════════════════════════════════════════════════════════
#  ASSETS
# ═══════════════════════════════════════════════════════════════════════════════

START_IMG_URL = "https://envs.sh/BjZ.jpg"

MESSAGE = f"""**๏ ᴛʜɪs ɪs ᴀᴅᴠᴀɴᴄᴇᴅ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘs + ᴄʜᴀɴɴᴇʟs ᴠᴄ. 💌

🎧 ᴘʟᴀʏ + ᴠᴘʟᴀʏ + ᴄᴘʟᴀʏ 🎧

➥ sᴜᴘᴘᴏʀᴛᴇᴅ ᴡᴇʟᴄᴏᴍᴇ - ʟᴇғᴛ ɴᴏᴛɪᴄᴇ, ᴛᴀɢᴀʟʟ, ᴠᴄᴛᴀɢ, ʙᴀɴ - ᴍᴜᴛᴇ, sʜᴀʏʀɪ, ʟᴜʀɪᴄs, sᴏɴɢ - ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅ, ᴇᴛᴄ... ❤️

🔐ᴜꜱᴇ » [/start](https://t.me/{{username}}?start=help) ᴛᴏ ᴄʜᴇᴄᴋ ʙᴏᴛ

➲ ʙᴏᴛ :** @{{username}}"""

TEXT = """**ᴀᴜᴛᴏ ɢᴄᴀsᴛ ɪs ᴇɴᴀʙʟᴇᴅ sᴏ ᴀᴜᴛᴏ ɢᴄᴀsᴛ/ʙʀᴏᴀᴅᴄᴀsᴛ ɪs ᴅᴏɪɴɢ ɪɴ ᴀʟʟ ᴄʜᴀᴛs ᴏɴ sᴄʜᴇᴅᴜʟᴇᴅ ᴛɪᴍᴇ.**\n**ɪᴛ ᴄᴀɴ ʙᴇ sᴛᴏᴘᴘᴇᴅ ʙʏ ᴘᴜᴛ ᴠᴀʀɪᴀʙʟᴇ [ᴀᴜᴛᴏ_ɢᴄᴀsᴛ = (Off)]**"""

# ═══════════════════════════════════════════════════════════════════════════════
#  KEYBOARD
# ═══════════════════════════════════════════════════════════════════════════════

BUTTON = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "๏ ᴀᴅᴅ ᴍᴇ ๏",
                url="https://t.me/aaru_music_rbot?startgroup=s&admin=delete_messages+manage_video_chats+pin_messages+invite_users",
            )
        ]
    ]
)

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def send_text_once() -> None:
    try:
        await app.send_message(LOG_GROUP_ID, TEXT)
    except Exception:
        pass


async def send_message_to_chats() -> None:
    try:
        me = await app.get_me()
        username = me.username
        caption = AUTO_GCAST_MSG if AUTO_GCAST_MSG else MESSAGE.replace("{username}", username)

        chats = await get_served_chats()
        for chat_info in chats:
            chat_id = chat_info.get("chat_id")
            if isinstance(chat_id, int):
                try:
                    await app.send_photo(
                        chat_id,
                        photo=START_IMG_URL,
                        caption=caption,
                        reply_markup=BUTTON,
                    )
                    await asyncio.sleep(3)
                except Exception:
                    pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

_broadcast_done: set[str] = set()


async def continuous_broadcast() -> None:
    await send_text_once()

    while True:
        if AUTO_GCASTS:
            now = datetime.datetime.now(IST)
            current_time = now.strftime("%H:%M")

            # Naya din aaya — done set reset karo
            if current_time == "00:01":
                _broadcast_done.clear()

            if current_time in SCHEDULED_TIMES and current_time not in _broadcast_done:
                _broadcast_done.add(current_time)
                try:
                    await send_message_to_chats()
                except Exception:
                    pass

                # Slot ke baad 60s wait — same minute mein dobara trigger nahi hoga
                await asyncio.sleep(60)
                continue

        await asyncio.sleep(30)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if AUTO_GCASTS:
    asyncio.create_task(continuous_broadcast())
```

---

Sirf ek cheez badli — **timing**:

| Purana | Naya (har 5 ghante) |
|--------|---------------------|
| 05:00 | 00:00 (midnight) |
| 09:00 | 05:00 |
| 14:00 | 10:00 |
| 17:00 | 15:00 |
| 19:00 | 20:00 |
| 00:00 | ✗ (5 slots kafi hain) |

Baaki sab — look, buttons, logic — exactly purana wala rakha hai.
