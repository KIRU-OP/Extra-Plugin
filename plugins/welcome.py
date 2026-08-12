import os
from unidecode import unidecode
from PIL import ImageDraw, Image, ImageFont, ImageChops
from pyrogram import *
from pyrogram.types import *
from logging import getLogger
from VIPMUSIC import LOGGER
from pyrogram.types import Message
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC import app
from motor.motor_asyncio import AsyncIOMotorClient

LOGGER = getLogger(__name__)

# ---------------------------------------------------------------------
# Self-contained Mongo connection for this plugin (welcome on/off state)
# ---------------------------------------------------------------------
def _get_mongo_uri():
    # Try to read the URI from config.py first (common variable names)
    try:
        import config
        for name in ("MONGO_DB_URI", "DATABASE_URL", "MONGODB_URI", "MONGO_URI"):
            uri = getattr(config, name, None)
            if uri:
                return uri
    except Exception as e:
        LOGGER.warning(f"Could not import config.py: {e}")

    # Fallback: check environment variables directly
    for name in ("MONGO_DB_URI", "DATABASE_URL", "MONGODB_URI", "MONGO_URI"):
        uri = os.environ.get(name)
        if uri:
            return uri

    raise RuntimeError(
        "MongoDB URI not found. Set MONGO_DB_URI (or DATABASE_URL) in config.py or as an env variable."
    )


_mongo_client = AsyncIOMotorClient(_get_mongo_uri())
_wdb = _mongo_client["VIPMUSIC"]  # change db name here if your bot uses a different one
wlcm = _wdb["welcome"]


async def add_wlcm(chat_id: int):
    return await wlcm.update_one(
        {"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True
    )


async def rm_wlcm(chat_id: int):
    return await wlcm.delete_one({"chat_id": chat_id})

__MODULE__ = "welcome"
__HELP__ = """
### Exᴀᴍᴘᴇs
- /wle on: Eɴᴀʙᴇs ᴀᴜᴛᴏ-ᴡᴇᴄᴏᴍᴇ.
- /wle off: Dɪsᴀʙᴇs ᴀᴜᴛᴏ-ᴡᴇᴄᴏᴍᴇ.
"""


class temp:
    ME = None
    CURRENT = 2
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None


def circle(pfp, size=(450, 450)):
    pfp = pfp.resize(size, Image.LANCZOS).convert("RGBA")
    bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(pfp.size, Image.LANCZOS)
    mask = ImageChops.darker(mask, pfp.split()[-1])
    pfp.putalpha(mask)
    return pfp


def welcomepic(pic, user, chat, id, uname):
    background = Image.open("assets/welcome.png")
    pfp = Image.open(pic).convert("RGBA")
    pfp = circle(pfp)
    pfp = pfp.resize((450, 450))
    draw = ImageDraw.Draw(background)
    font = ImageFont.truetype('assets/font.ttf', size=45)
    font2 = ImageFont.truetype('assets/font.ttf', size=90)
    draw.text((65, 250), f'NAME : {unidecode(user)}', fill="white", font=font)
    draw.text((65, 340), f'ID : {id}', fill="white", font=font)
    draw.text((65, 430), f"USERNAME : {uname}", fill="white", font=font)
    pfp_position = (767, 133)
    background.paste(pfp, pfp_position, pfp)
    background.save(f"downloads/welcome#{id}.png")
    return f"downloads/welcome#{id}.png"


@app.on_message(filters.command(["welcome", "wle"]) & ~filters.private)
async def auto_state(_, message):
    usage = "**❖ ᴜsᴀɢᴇ ➥** /wle [on|off]"
    if len(message.command) == 1:
        return await message.reply_text(usage)

    chat_id = message.chat.id
    user = await app.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in (
        enums.ChatMemberStatus.ADMINISTRATOR,
        enums.ChatMemberStatus.OWNER,
    ):
        return await message.reply("✦ Only Admins Can Use This Command")

    A = await wlcm.find_one({"chat_id": chat_id})
    state = message.text.split(None, 1)[1].strip().lower()

    # "on"/"enable" and "off"/"disable" both accepted
    if state in ("on", "enable"):
        if A:
            return await message.reply_text("✦ Special Welcome Already Enabled")
        await add_wlcm(chat_id)
        await message.reply_text(f"✦ Enabled Special Welcome in {message.chat.title}")

    elif state in ("off", "disable"):
        if not A:
            return await message.reply_text("✦ Special Welcome Already Disabled")
        await rm_wlcm(chat_id)
        await message.reply_text(f"✦ Disabled Special Welcome in {message.chat.title}")

    else:
        await message.reply_text(usage)


@app.on_chat_member_updated(filters.group, group=-3)
async def greet_group(_, member: ChatMemberUpdated):
    chat_id = member.chat.id
    A = await wlcm.find_one({"chat_id": chat_id})
    if not A:
        return

    if (
        not member.new_chat_member
        or member.new_chat_member.status in {"banned", "left", "restricted"}
        or member.old_chat_member
    ):
        return

    user = member.new_chat_member.user if member.new_chat_member else member.from_user
    try:
        pic = await app.download_media(
            user.photo.big_file_id, file_name=f"pp{user.id}.png"
        )
    except AttributeError:
        pic = "assets/upic.png"

    if (temp.MELCOW).get(f"welcome-{member.chat.id}") is not None:
        try:
            await temp.MELCOW[f"welcome-{member.chat.id}"].delete()
        except Exception as e:
            LOGGER.error(e)

    try:
        welcomeimg = welcomepic(
            pic, user.first_name, member.chat.title, user.id, user.username
        )
        temp.MELCOW[f"welcome-{member.chat.id}"] = await app.send_photo(
            member.chat.id,
            photo=welcomeimg,
            caption=f"""
 •●◉✿ ᴡᴇʟᴄᴏᴍᴇ ʙᴀʙʏ ✿◉●•
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▰

● ɴᴀᴍᴇ ➥  {user.mention}
● ᴜsᴇʀɴᴀᴍᴇ ➥  @{user.username}
● ᴜsᴇʀ ɪᴅ ➥  {user.id}

❖ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ➥ ˹ᴀᴀʀᴜ ꭙ ᴍᴜsɪᴄ˼ ♡゙
▰▱▱▱▱▱▱▱▱▱▱▱▱▱▰
""",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ",
                            url=f"https://t.me/{app.username}?startgroup=True",
                        ),
                    ]
                ]
            ),
        )

    except Exception as e:
        LOGGER.error(e)
    try:
        os.remove(f"downloads/welcome#{user.id}.png")
        os.remove(f"downloads/pp{user.id}.png")
    except Exception:
        pass
