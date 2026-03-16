import os
import re
import time
import asyncio
import logging
import math

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from plugins.antinsfw import check_anti_nsfw
from helper.database import codeflixbots
from helper.auth import auth_chats
from helper.permissions import is_owner, is_admin as _perm_is_admin, is_authorized_chat
from config import Config

import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_queue = asyncio.Queue()
processing = False

queue_users = {}
current_user = None

cancel_tasks = set()
task_owner_map = {}   # task_token -> user_id (server-side verification)
select_sessions = {}

# ================= ADMIN CHECK =================

def _is_admin_rename(user_id):
    return _perm_is_admin(user_id)


# ================= ADMIN COMMANDS =================

@Client.on_message((filters.private | filters.group) & filters.command("add"))
async def add_admin(client, message):

    # Sirf owner use kar sake
    if message.from_user.id != Config.OWNER_ID:
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    if not message.reply_to_message:
        return await message.reply_text("❌ Kisi user ko reply karo")

    new_admin = message.reply_to_message.from_user.id

    if new_admin == Config.OWNER_ID:
        return await message.reply_text("❌ Owner already owner hai")

    if new_admin in Config.ADMIN:
        return await message.reply_text("⚠️ Yeh already admin hai")

    Config.ADMIN.append(new_admin)
    await message.reply_text(f"✅ Admin add kiya\n\n`{new_admin}`")


@Client.on_message((filters.private | filters.group) & filters.command("rm"))
async def remove_admin(client, message):

    # Sirf owner use kar sake
    if message.from_user.id != Config.OWNER_ID:
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    if not message.reply_to_message:
        return await message.reply_text("❌ Kisi admin ko reply karo")

    user_id = message.reply_to_message.from_user.id

    if user_id == Config.OWNER_ID:
        return await message.reply_text("❌ Owner ko remove nahi kar sakte")

    if user_id in Config.ADMIN:
        Config.ADMIN.remove(user_id)
        await message.reply_text(f"✅ Admin remove kiya\n\n`{user_id}`")
    else:
        await message.reply_text("⚠️ Yeh admin nahi hai")


@Client.on_message((filters.private | filters.group) & filters.command("addlist"))
async def admin_list(client, message):

    # Sirf owner use kar sake
    if message.from_user.id != Config.OWNER_ID:
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    text = "👑 **Admin List**\n\n"
    text += f"👑 Owner: `{Config.OWNER_ID}`\n\n"

    if Config.ADMIN:
        for admin in Config.ADMIN:
            text += f"• `{admin}`\n"
    else:
        text += "No admins added yet"

    await message.reply_text(text)



# ================= REGEX =================

SEASON_EPISODE_PATTERN = re.compile(
    r"[Ss][ ._\-]?(\d{1,3})[ ._\-]?[Ee][ ._\-]?(\d{1,3})|" 
    r"[Ss](\d{1,3})[ ._\-]+(\d{1,3})|" 
    r"(\d{1,3})x(\d{1,3})|" 
    r"[Ee]pisode[ ._\-]?(\d{1,3})",
    re.IGNORECASE
)

QUALITY_PATTERN = re.compile(r"(\d{2,4}p)", re.IGNORECASE)


# ================= PROGRESS =================

_last_edit_times = {}  # message_id -> last edit time

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if diff <= 0:
        return

    # Throttle: har 5 seconds mein ek baar edit karo
    msg_id = message.id
    last = _last_edit_times.get(msg_id, 0)
    if now - last < 5 and current != total:
        return
    _last_edit_times[msg_id] = now

    percentage = current * 100 / total if total else 0
    speed = current / diff if diff else 0
    eta = (total - current) / speed if speed else 0

    filled = "⬢" * int(percentage / 10)
    empty = "⬡" * (10 - int(percentage / 10))

    text = (
        f"{ud_type}\n\n"
        f"{filled}{empty} {round(percentage, 2)}%\n\n"
        f"📦 {humanbytes(current)} / {humanbytes(total)}\n"
        f"⚡ {humanbytes(speed)}/s\n"
        f"⏳ {TimeFormatter(eta*1000)}"
    )

    try:
        from pyrogram.errors import FloodWait
        await message.edit(text)
        if current == total:
            _last_edit_times.pop(msg_id, None)
    except FloodWait as e:
        _last_edit_times[msg_id] = now + e.value
    except:
        pass


def humanbytes(size):

    if not size:
        return "0 B"

    power = 1024
    n = 0
    Dic = {0: "B", 1: "KB", 2: "MB", 3: "GB"}

    while size > power:
        size /= power
        n += 1

    return f"{round(size,2)} {Dic[n]}"


def TimeFormatter(milliseconds):

    seconds = int(milliseconds / 1000)

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours}h {minutes}m {seconds}s"


# ================= HELPERS =================

def extract_season_episode(filename):

    match = SEASON_EPISODE_PATTERN.search(filename)

    if not match:
        return None, None

    g = match.groups()

    if g[0] and g[1]:
        return g[0].zfill(2), g[1].zfill(2)

    if g[2] and g[3]:
        return g[2].zfill(2), g[3].zfill(2)

    if g[4] and g[5]:
        return g[4].zfill(2), g[5].zfill(2)

    if g[6]:
        return "01", g[6].zfill(2)

    return None, None


def extract_quality(filename):

    match = QUALITY_PATTERN.search(filename)

    return match.group(1) if match else "Unknown"


async def cleanup_files(*paths):

    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except:
            pass



# ================= SELECT =================

@Client.on_message((filters.private | filters.group) & filters.command("select"))
async def select_range(client, message):

    if not _is_admin_rename(message.from_user.id):
        return await message.reply_text("❌ Only admins can use this command")

    try:
        args = message.text.split()[1]
        start, end = map(int, args.split("-"))

        if start < 1 or end < start:
            return await message.reply_text("❌ Invalid range\nExample: /select 1-12")

        select_sessions[message.from_user.id] = {
            "start": start,
            "end": end,
            "count": 0,
        }

        await message.reply_text(
            f"✅ Rename range set\n\n"
            f"📌 Start: {start}\n"
            f"📌 End: {end}\n"
            f"📦 Total files: {end - start + 1}\n\n"
            f"Now send your files!"
        )

    except (IndexError, ValueError):
        await message.reply_text(
            "❌ Wrong format\n\n"
            "Usage: `/select 1-12`\n"
            "Example: `/select 3-8` — files 3 to 8 rename karega"
        )


# ================= QUEUE =================

@Client.on_message((filters.private | filters.group) & filters.command("queue"))
async def show_queue(client, message):

    text = "📦 Rename Queue\n\n"

    if current_user:
        text += f"⚙️ Processing: {current_user}\n\n"

    if not queue_users:
        text += "Queue empty"

    else:

        i = 1

        for user, count in queue_users.items():
            text += f"{i}. {user} — {count} files\n"
            i += 1

    await message.reply_text(text)


# ================= HANDLE FILE =================

@Client.on_message(
    (filters.private | filters.group)
    & (filters.document | filters.video | filters.audio)
    & ~filters.command(["encode", "autorename", "setmedia", "sequence", "done"]),
    group=1
)
async def handle_files(client, message):

    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return

    # Group auth check
    if message.chat.type in ["group", "supergroup"]:
        if not is_authorized_chat(message.chat.id):
            return

    # Sirf admin/owner files bhej sake
    if not _is_admin_rename(user_id):
        return

    if user_id not in select_sessions:
        return

    session = select_sessions[user_id]

    session["count"] += 1

    if session["count"] < session["start"]:
        return

    if session["count"] > session["end"]:
        del select_sessions[user_id]
        return

    user = message.from_user.first_name

    queue_users[user] = queue_users.get(user, 0) + 1

    position = file_queue.qsize() + 1

    await message.reply_text(
        f"📥 Added to Queue\n\n"
        f"User: {message.from_user.mention}\n"
        f"Position: {position}"
    )

    await file_queue.put((client, message))

    asyncio.create_task(process_queue())


# ================= PROCESS QUEUE =================

async def process_queue():

    global processing, current_user

    if processing:
        return

    processing = True

    while not file_queue.empty():

        client, message = await file_queue.get()

        current_user = message.from_user.first_name

        try:
            await auto_rename_files(client, message)
        except Exception as e:
            logger.error(e)

        user = message.from_user.first_name

        if user in queue_users:
            queue_users[user] -= 1
            if queue_users[user] <= 0:
                del queue_users[user]

        file_queue.task_done()

    current_user = None
    processing = False


# ================= CANCEL =================

@Client.on_callback_query(filters.regex("^cancel_"))
async def cancel_task_rename(client, query):

    token = query.data  # e.g. "cancel_1712345678123"
    caller_id = query.from_user.id

    # Server-side check — task_owner_map mein dekho asli owner kaun hai
    owner_id = task_owner_map.get(token)

    if owner_id is None:
        return await query.answer("❌ Task not found or already done", show_alert=True)

    if caller_id != owner_id and not is_admin(caller_id):
        return await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)

    cancel_tasks.add(owner_id)
    await query.answer("✅ Cancel request sent")


# ================= LOGS COMMAND =================

class TelegramLogHandler(logging.Handler):
    """Log messages ko Telegram pe bhejta hai"""
    def __init__(self):
        super().__init__()
        self._client = None
        self._target = None
        self._buffer = []
        self._active = False

    def setup(self, client, target):
        self._client = client
        self._target = target
        self._active = True

    def stop(self):
        self._active = False
        self._client = None
        self._target = None

    def emit(self, record):
        if self._active and self._client and self._target:
            try:
                msg = self.format(record)
                self._buffer.append(msg)
            except:
                pass

telegram_log_handler = TelegramLogHandler()
telegram_log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
)


@Client.on_message((filters.private | filters.group) & filters.command("logs"))
async def send_logs(client, message):

    user_id = message.from_user.id

    if not _is_admin_rename(user_id):
        return await message.reply_text("❌ Only admins and owner can use this command")

    args = message.text.split()

    # /logs stop
    if len(args) > 1 and args[1] == "stop":
        if telegram_log_handler._active:
            telegram_log_handler.stop()
            logging.getLogger().removeHandler(telegram_log_handler)
            await message.reply_text("🔕 Log streaming stopped")
        else:
            await message.reply_text("ℹ️ Log streaming is not active")
        return

    # /logs — last logs file se bhejo
    log_lines = []
    try:
        # Try reading from log buffer first
        if telegram_log_handler._buffer:
            log_lines = telegram_log_handler._buffer[-50:]
        else:
            # Fallback: recent log messages collect karo
            log_lines = ["No recent logs buffered. Start streaming with /logs stream"]
    except:
        log_lines = ["Could not read logs"]

    if len(args) > 1 and args[1] == "stream":
        # Start live streaming
        if telegram_log_handler._active:
            await message.reply_text("ℹ️ Already streaming logs to this chat")
            return
        telegram_log_handler.setup(client, message.chat.id)
        logging.getLogger().addHandler(telegram_log_handler)
        await message.reply_text(
            "📡 **Log streaming started**\n\n"
            "Logs will be sent here in real-time\n"
            "Use `/logs stop` to stop streaming"
        )
        # Start async sender
        asyncio.create_task(_send_log_buffer(client, message.chat.id))
        return

    # Show recent buffered logs
    if log_lines:
        text = "📋 **Recent Logs**\n\n`" + "\n".join(log_lines[-30:]) + "`"
        # Telegram message limit 4096 chars
        if len(text) > 4000:
            text = "📋 **Recent Logs**\n\n`" + "\n".join(log_lines[-10:]) + "`"
        await message.reply_text(text)
    else:
        await message.reply_text(
            "📋 No logs buffered yet\n\n"
            "Use `/logs stream` to start live log streaming"
        )


async def _send_log_buffer(client, chat_id):
    """Background task — buffer se logs Telegram pe bhejta hai"""
    sent_count = 0
    while telegram_log_handler._active:
        await asyncio.sleep(10)  # har 10 seconds mein batch bhejo
        if not telegram_log_handler._buffer:
            continue
        # Naye logs nikalo
        new_logs = telegram_log_handler._buffer[sent_count:]
        if not new_logs:
            continue
        sent_count = len(telegram_log_handler._buffer)
        text = "\n".join(new_logs[-20:])
        if len(text) > 3800:
            text = text[-3800:]
        try:
            await client.send_message(chat_id, f"📡 **Live Logs**\n\n`{text}`")
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except:
            pass
        # Buffer ko 200 lines tak rakho
        if len(telegram_log_handler._buffer) > 200:
            telegram_log_handler._buffer = telegram_log_handler._buffer[-200:]
            sent_count = len(telegram_log_handler._buffer)


# ================= MAIN RENAME =================

async def auto_rename_files(client, message: Message):

    user_id = message.from_user.id

    format_template = await codeflixbots.get_format_template(user_id)

    if not format_template:
        return await message.reply_text(
            "⚠️ Set rename format using /autorename"
        )

    file = message.document or message.video or message.audio

    file_name = file.file_name

    if await check_anti_nsfw(file_name, message):
        return

    season, episode = extract_season_episode(file_name)
    quality = extract_quality(file_name)

    format_template = (
        format_template.replace("{season}", season or "XX")
        .replace("{episode}", episode or "XX")
        .replace("{quality}", quality)
    )

    ext = os.path.splitext(file_name)[1]

    safe_filename = re.sub(r"[^\w\-. \[\]@-]", "", f"{format_template}{ext}")

    os.makedirs("downloads", exist_ok=True)

    download_path = f"downloads/{time.time()}_{safe_filename}"

    # Unique token — koi guess nahi kar sakta
    task_token = f"cancel_{int(time.time() * 1000)}_{user_id}"
    task_owner_map[task_token] = user_id

    msg = await message.reply_text(
        "📥 Downloading...",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=task_token)]]
        ),
    )

    start = time.time()

    file_path = await client.download_media(
        message,
        file_name=download_path,
        progress=progress_for_pyrogram,
        progress_args=("📥 Downloading...", msg, start),
    )

    # Cancel check after download
    if user_id in cancel_tasks:
        cancel_tasks.discard(user_id)
        await cleanup_files(file_path)
        await msg.edit("❌ Task Cancelled")
        return

    try:

        await msg.edit("⚙️ Applying Metadata...")

        title = await codeflixbots.get_title(user_id) or ""
        author = await codeflixbots.get_author(user_id) or ""
        artist = await codeflixbots.get_artist(user_id) or ""

        meta_file = f"downloads/meta_{safe_filename}"

        cmd = [
            "ffmpeg", "-i", file_path,
            "-map", "0", "-c", "copy",
            "-metadata", f"title={title}",
            "-metadata", f"author={author}",
            "-metadata", f"artist={artist}",
            "-metadata", "encoder=SharkToonsIndia",
            "-y", meta_file,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.warning(f"Metadata ffmpeg error: {stderr.decode()}")
            raise Exception("ffmpeg failed")

        # Cancel check after metadata
        if user_id in cancel_tasks:
            cancel_tasks.discard(user_id)
            await cleanup_files(file_path, meta_file)
            await msg.edit("❌ Task Cancelled")
            return

        await cleanup_files(file_path)
        file_path = meta_file
        logger.info(f"Metadata applied for user {user_id}")

    except Exception as e:
        logger.warning(f"Metadata skipped: {e}")
        await msg.edit("⚙️ Processing without metadata")

    thumb = None

    thumb_id = await codeflixbots.get_thumbnail(user_id)

    if thumb_id:

        try:
            thumb = await client.download_media(
                thumb_id,
                file_name=f"thumb_{user_id}.jpg"
            )
        except:
            thumb = None

    caption = safe_filename

    await msg.edit(
        "🚀 Uploading...",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=task_token)]]
        ),
    )

    start = time.time()
    flood_wait_until = 0  # FloodWait tracker

    while True:

        if user_id in cancel_tasks:
            cancel_tasks.discard(user_id)
            await cleanup_files(file_path, thumb)
            await msg.edit("❌ Task Cancelled")
            return

        # FloodWait active hai toh skip karo, block mat karo
        now = time.time()
        if now < flood_wait_until:
            await asyncio.sleep(2)
            continue

        try:

            await client.send_document(
                chat_id=user_id,          # ✅ hamesha DM mein bhejo
                document=file_path,
                file_name=safe_filename,
                caption=caption,
                thumb=thumb,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Uploading...", msg, start),
            )

            break

        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s on upload for user {user_id}")
            flood_wait_until = time.time() + e.value  # block nahi, sirf track karo
            try:
                await msg.edit(f"⏳ Rate limited — resuming in {e.value}s...")
            except:
                pass

        except Exception as e:
            logger.error(f"Upload error for user {user_id}: {e}")
            await asyncio.sleep(5)

    # ---- Group mein original file delete karo ----
    if message.chat.type in ["group", "supergroup"]:
        try:
            await message.delete()  # ✅ hamesha try karo — permission ho ya na ho
        except:
            pass  # Permission nahi hai toh skip

    await cleanup_files(file_path, thumb)  # ✅ hamesha cleanup

    # Token cleanup — task khatam, map se hata do
    task_owner_map.pop(task_token, None)

    try:
        await msg.delete()
    except:
        pass
