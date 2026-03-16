import os
import sys
import time
import asyncio
import logging
from collections import deque

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from helper.utils import progress_for_pyrogram
from helper.auth import auth_chats
from helper.database import codeflixbots
from helper.permissions import is_owner, is_admin as _perm_is_admin
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ================= ADMIN CHECK =================

def is_admin(user_id):
    return user_id == Config.OWNER_ID or _perm_is_admin(user_id)

# ================= COMPRESS LEVELS =================

COMPRESS_LEVELS = {
    "low": {
        "label": "🟢 Low",
        "crf": 26,
        "desc": "~10% smaller · best quality"
    },
    "medium": {
        "label": "🟡 Medium",
        "crf": 28,
        "desc": "~30% smaller · good quality"
    },
    "high": {
        "label": "🟠 High",
        "crf": 31,
        "desc": "~50% smaller · decent quality"
    },
    "best": {
        "label": "🔴 Best",
        "crf": 35,
        "desc": "~70% smaller · max compression"
    },
}

# ================= QUEUE =================

compress_queue = asyncio.Queue()
queue_list = deque()
active_tasks = {}
workers_started = False
cancel_tasks = {}
compress_wait = {}  # user_id -> {"msg": message}

# ================= WORKER =================

async def start_workers(client):
    global workers_started
    if workers_started:
        return
    workers_started = True
    asyncio.create_task(worker(client))


async def worker(client):
    while True:
        task = await compress_queue.get()
        active_tasks[task["id"]] = task
        try:
            await run_compress(client, task)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        active_tasks.pop(task["id"], None)
        try:
            queue_list.remove(task)
        except:
            pass
        compress_queue.task_done()


# ================= /compress COMMAND =================

@Client.on_message(
    (filters.private | filters.group) &
    filters.command("compress") &
    filters.reply
)
async def compress_cmd(client, message):
    user_id = message.from_user.id

    # Sirf owner aur admins use kar sakte hain
    if not is_admin(user_id):
        await message.reply_text("❌ Sirf owner aur admins use kar sakte hain")
        return

    # Group mein auth check
    if message.chat.type in ["group", "supergroup"]:
        if message.chat.id not in auth_chats:
            await message.reply_text("❌ This group is not authorized")
            return

    replied = message.reply_to_message

    if not (replied.video or replied.document):
        await message.reply_text("❌ Reply to a video or file")
        return

    is_group = message.chat.type in ["group", "supergroup"]
    compress_wait[user_id] = {"msg": replied, "is_group": is_group}

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Low", callback_data=f"compress_level|{user_id}|low"),
            InlineKeyboardButton("🟡 Medium", callback_data=f"compress_level|{user_id}|medium"),
        ],
        [
            InlineKeyboardButton("🟠 High", callback_data=f"compress_level|{user_id}|high"),
            InlineKeyboardButton("🔴 Best", callback_data=f"compress_level|{user_id}|best"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"compress_cancel_pre|{user_id}"),
        ]
    ])

    dm_note = "\n\n📩 _Result will be sent to your DM_" if is_group else ""

    await message.reply_text(
        "🗜️ **Video Compressor**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 **Low** — ~10% smaller · best quality\n"
        "🟡 **Medium** — ~30% smaller · good quality\n"
        "🟠 **High** — ~50% smaller · decent quality\n"
        "🔴 **Best** — ~70% smaller · max compression\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 **Select compression level:**{dm_note}",
        reply_markup=buttons
    )

    await start_workers(client)


# ================= LEVEL SELECT =================

@Client.on_callback_query(filters.regex("^compress_level"))
async def compress_level_select(client, query):
    _, user_id, level = query.data.split("|")
    user_id = int(user_id)

    if query.from_user.id != user_id:
        await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)
        return

    data = compress_wait.pop(user_id, None)
    if not data:
        await query.answer("Session expired. Send /compress again.", show_alert=True)
        return

    level_info = COMPRESS_LEVELS[level]
    task = {
        "id": int(time.time() * 1000),
        "user": user_id,
        "level": level,
        "crf": level_info["crf"],
        "label": level_info["label"],
        "msg": data["msg"],
        "name": query.from_user.first_name,
        "is_group": data.get("is_group", False),
    }

    queue_list.append(task)
    cancel_tasks[task["id"]] = False

    pos = compress_queue.qsize() + 1
    await query.message.edit_text(
        f"📥 Added to Queue\n\n"
        f"{level_info['label']} — {level_info['desc']}\n"
        f"📌 Position: {pos}"
    )

    await compress_queue.put(task)


# ================= PRE-CANCEL =================

@Client.on_callback_query(filters.regex("^compress_cancel_pre"))
async def compress_cancel_pre(client, query):
    _, user_id = query.data.split("|")
    user_id = int(user_id)

    if query.from_user.id != user_id:
        await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)
        return

    compress_wait.pop(user_id, None)
    await query.message.edit_text("❌ Compress cancelled.")


# ================= CANCEL =================

@Client.on_callback_query(filters.regex("^compress_cancel[|]"))
async def compress_cancel(client, query):
    _, task_id, user_id = query.data.split("|")
    task_id = int(task_id)
    user_id = int(user_id)
    caller_id = query.from_user.id

    # Task owner — cancel kar sakta hai
    if caller_id == user_id:
        pass
    # Owner — kisi ka bhi cancel kar sakta hai
    elif caller_id == Config.OWNER_ID:
        pass
    # Admin — sirf apna cancel kar sakta hai, dusre admin ka nahi
    else:
        await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)
        return

    cancel_tasks[task_id] = True
    await query.answer("❌ Cancelling...")


# ================= /ctasks COMMAND =================

@Client.on_message(
    (filters.private | filters.group) & filters.command("ctasks")
)
async def compress_tasks_cmd(client, message):
    if not is_admin(message.from_user.id):
        return

    if not active_tasks and compress_queue.empty():
        return await message.reply_text("✅ No active compress tasks")

    text = "🗜️ **Compress Tasks**\n\n"

    for task_id, task in active_tasks.items():
        text += (
            f"⚙️ **Running**\n"
            f"👤 User: `{task['user']}`\n"
            f"📊 Level: {task['label']}\n"
            f"🆔 ID: `{task_id}`\n\n"
        )

    if not compress_queue.empty():
        text += f"📦 Queue: `{compress_queue.qsize()}` pending\n"

    await message.reply_text(text)


# ================= RUN COMPRESS =================

async def run_compress(client, task):
    msg = task["msg"]
    user_id = task["user"]
    crf = task["crf"]
    label = task["label"]
    task_id = task["id"]

    cancel_btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data=f"compress_cancel|{task_id}|{user_id}")]]
    )

    os.makedirs("downloads", exist_ok=True)
    download = f"downloads/comp_in_{task_id}.mkv"
    output = f"downloads/comp_out_{task_id}.mkv"
    file_path = None

    try:
        # ---------------- DOWNLOAD ----------------
        progress_msg = await msg.reply_text(
            "📥 Downloading...",
            reply_markup=cancel_btn
        )

        start_time = time.time()
        logger.info(f"[{task_id}] Compress download started | user={user_id}")

        file_path = await client.download_media(
            msg,
            file_name=download,
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", progress_msg, start_time)
        )

        logger.info(f"[{task_id}] Download complete: {file_path}")

        if cancel_tasks.get(task_id):
            await progress_msg.edit("❌ Download Cancelled")
            return

        # ---------------- COMPRESS ----------------
        await progress_msg.edit(
            f"🗜️ Compressing... {label}\n\n⬡⬡⬡⬡⬡⬡⬡⬡⬡⬡ 0%",
            reply_markup=cancel_btn
        )

        # Get original size
        orig_size = os.path.getsize(file_path)

        cmd = [
            "ffmpeg",
            "-progress", "pipe:1",
            "-nostats",
            "-i", file_path,
            "-map", "0",
            "-c:v", "libx265",
            "-preset", "veryfast",
            "-crf", str(crf),
            "-x265-params", "log-level=error",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-c:s", "copy",
            "-y",
            output
        ]

        logger.info(f"[{task_id}] Compress started | level={task['level']} crf={crf}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        progress = 0
        last_edit = 0

        while True:
            if cancel_tasks.get(task_id):
                process.kill()
                await progress_msg.edit("❌ Compress Cancelled")
                return

            line = await process.stdout.readline()
            if not line:
                break

            text = line.decode("utf-8")
            if "out_time=" in text:
                progress = min(progress + 2, 100)
                now = time.time()
                if now - last_edit >= 8:
                    last_edit = now
                    filled = "⬢" * (progress // 10)
                    empty = "⬡" * (10 - progress // 10)
                    try:
                        await progress_msg.edit(
                            f"🗜️ Compressing... {label}\n\n{filled}{empty} {progress}%",
                            reply_markup=cancel_btn
                        )
                    except FloodWait as e:
                        last_edit = time.time() + e.value
                    except:
                        pass

        await process.wait()
        logger.info(f"[{task_id}] Compress complete")

        try:
            await progress_msg.edit(
                f"🗜️ Compressing... {label}\n\n⬢⬢⬢⬢⬢⬢⬢⬢⬢⬢ 100% ✅"
            )
        except:
            pass

        if not os.path.exists(output):
            await progress_msg.edit("❌ Compress failed — output not found")
            return

        # Size comparison
        new_size = os.path.getsize(output)
        saved = orig_size - new_size
        saved_pct = round((saved / orig_size) * 100, 1) if orig_size else 0

        # ---------------- RENAME ----------------
        if msg.document and msg.document.file_name:
            name = msg.document.file_name
        elif msg.video and msg.video.file_name:
            name = msg.video.file_name
        else:
            name = f"compressed_{task_id}.mkv"

        name = os.path.splitext(name)[0] + ".mkv"

        # ---------------- METADATA ----------------
        title = await codeflixbots.get_title(user_id) or ""
        author = await codeflixbots.get_author(user_id) or ""
        artist = await codeflixbots.get_artist(user_id) or ""

        meta_file = f"downloads/meta_{task_id}.mkv"
        meta_cmd = [
            "ffmpeg",
            "-i", output,
            "-map", "0",
            "-c", "copy",
            "-metadata", f"title={title}",
            "-metadata", f"author={author}",
            "-metadata", f"artist={artist}",
            "-metadata", "encoder=SharkToonsIndia",
            "-y", meta_file
        ]

        await progress_msg.edit("🗜️ Adding metadata...")
        meta_proc = await asyncio.create_subprocess_exec(
            *meta_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await meta_proc.wait()

        if os.path.exists(meta_file):
            os.remove(output)
            output_final = meta_file
        else:
            output_final = output

        # ---------------- THUMB ----------------
        thumb = None
        thumb_id = await codeflixbots.get_thumbnail(user_id)
        if thumb_id:
            try:
                thumb = await client.download_media(
                    thumb_id,
                    file_name=f"downloads/thumb_{task_id}.jpg"
                )
            except:
                thumb = None

        # ---------------- UPLOAD ----------------
        caption = (
            f"🗜️ **Compressed** — {label}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Original: `{round(orig_size/1024/1024, 2)} MB`\n"
            f"📦 Compressed: `{round(new_size/1024/1024, 2)} MB`\n"
            f"✅ Saved: `{round(saved/1024/1024, 2)} MB ({saved_pct}%)`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 `{name}`"
        )

        await progress_msg.edit(
            "📤 Uploading...",
            reply_markup=cancel_btn
        )

        start_time = time.time()
        logger.info(f"[{task_id}] Upload started")

        # Hamesha DM mein bhejo — group ho ya private
        while True:
            if cancel_tasks.get(task_id):
                await progress_msg.edit("❌ Upload Cancelled")
                return
            try:
                await client.send_document(
                    chat_id=user_id,  # hamesha DM
                    document=output_final,
                    file_name=name,
                    caption=caption,
                    thumb=thumb if thumb else None,
                    progress=progress_for_pyrogram,
                    progress_args=("📤 Uploading...", progress_msg, start_time)
                )
                break
            except FloodWait as e:
                await asyncio.sleep(e.value)

        logger.info(f"[{task_id}] Task complete | saved={saved_pct}%")
        await progress_msg.delete()

    except Exception as e:
        logger.error(f"[{task_id}] Error: {e}")
        try:
            await progress_msg.edit(f"❌ Error: {str(e)[:200]}")
        except:
            pass

    finally:
        cancel_tasks.pop(task_id, None)
        for f in [file_path, output, meta_file if 'meta_file' in dir() else None, thumb]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except:
                pass
