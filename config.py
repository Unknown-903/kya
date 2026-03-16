import re
import os
import time

id_pattern = re.compile(r'^.\d+$')


class Config(object):

    # ================= BOT CONFIG =================
    API_ID = int(os.environ.get("API_ID", 29776284))
    API_HASH = os.environ.get("API_HASH", "aa9d8ca9cf83f30aa897effa6296493a")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8142527078:AAFifGQPKZPIz2ZnGXIGOGYFlZdheNrmxec")

    # ================= OWNER =================
    OWNER_ID = int(os.environ.get("OWNER_ID", "7224871892"))

    # ================= DATABASE =================
    DB_NAME = os.environ.get("DB_NAME", "Yato")
    DB_URL = os.environ.get(
        "DB_URL",
        "mongodb+srv://Toonpro12:animebash@cluster0.e6hpn8l.mongodb.net/?retryWrites=true&w=majority"
    )

    PORT = int(os.environ.get("PORT", "8080"))

    # ================= BOT STATUS =================
    BOT_UPTIME = time.time()

    START_PIC = os.environ.get(
        "START_PIC",
        "https://graph.org/file/29a3acbbab9de5f45a5fe.jpg"
    )

    # ================= ADMINS =================
    ADMIN = [
        int(admin) if id_pattern.search(admin) else admin
        for admin in os.environ.get("ADMIN", "1889175355 7224871892").split()
    ]

    # ================= CHANNELS =================
    FORCE_SUB_CHANNELS = os.environ.get(
        "FORCE_SUB_CHANNELS",
        "sharktoonsindia"
    ).split(",")

    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002913785995"))
    DUMP_CHANNEL = int(os.environ.get("DUMP_CHANNEL", "-1002913785995"))

    # ================= WEBHOOK =================
    WEBHOOK = os.environ.get("WEBHOOK", "True").lower() == "true"


class Txt(object):

    START_TXT = """<b>ʜᴇʏ! {}

» ɪ ᴀᴍ ᴀᴅᴠᴀɴᴄᴇᴅ ʀᴇɴᴀᴍᴇ ʙᴏᴛ!
ɪ ᴄᴀɴ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ғɪʟᴇs ᴡɪᴛʜ
ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴀɴᴅ ᴛʜᴜᴍʙɴᴀɪʟ.</b>
"""

    FILE_NAME_TXT = """<b>Set Auto Rename Format

Example:
/autorename Anime Name S{season}E{episode} {quality}

Current Format:
{format_template}
</b>"""

    HELP_TXT = """<b>Important Commands

/autorename – Set rename format
/metadata – Turn metadata on/off
/queue – Show queue status
/restart – Restart bot (Owner only)
</b>"""

    PROGRESS_BAR = """
<b>» Size</b> : {1} | {2}
<b>» Done</b> : {0}%
<b>» Speed</b> : {3}/s
<b>» ETA</b> : {4}
"""
