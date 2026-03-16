import os
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
from helper.permissions import is_owner, is_admin as _perm_is_admin, is_authorized_chat
from config import Config

import sys

# Docker mein stdout pe force karo - tabhi logs `docker logs` mein dikhenge
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ================= ADMIN CHECK =================

def _is_admin_encode(user_id):
    return _perm_is_admin(user_id)

# ================= SETTINGS =================

RESOLUTIONS = {
    "480p": "854:480",
    "720p": "1280:720",
    "1080p": "1920:1080",
    "4k": "3840:2160"
}

DEFAULT_CRF = {
    "480p": 24,
    "720p": 23,
    "1080p": 22,
    "4k": 20
}

PRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "fast",
    "medium",
    "slow"
]

# Compress level: CRF values
COMPRESS_LEVELS = {
    "low":    {"crf_add": 2,  "label": "🟢 Low"},
    "medium": {"crf_add": 5,  "label": "🟡 Medium"},
    "high":   {"crf_add": 8,  "label": "🟠 High"},
    "best":   {"crf_add": 12, "label": "🔴 Best"},
}

# Patience messages — time lag raha ho toh dikhao
PATIENCE_MSGS = [
    "☕ Chai pi lo, thoda time lagega...",
    "🍿 Popcorn ready karo, abhi aa raha hai!",
    "😴 Thoda so jao, hum kaam kar rahe hain...",
    "🐢 H.265 encoding slow hoti hai, quality ke liye worth it hai!",
    "🔧 FFmpeg mehnat kar raha hai aapke liye...",
    "🎬 Hollywood movie bhi itni mehnat se banti hai!",
    "⚡ Server full speed pe hai, bas thoda sabr karo...",
    "🧘 Patience is a virtue... aur encoding bhi!",
    "🚀 Quality encode ho rahi hai, rush mat karo!",
    "💪 Jitna bada file, utna zyada time — normal hai!",
]

# ================= QUEUE =================

encode_queue = asyncio.Queue()
queue_list = deque()
active_tasks = {}
workers_started = False

rename_wait = {}
cancel_tasks = {}

# ================= WORKER =================

async def start_workers(client):
    global workers_started
    if workers_started:
        return
    workers_started = True
    asyncio.create_task(worker(client))


async def worker(client):
    while True:
        task = await encode_queue.get()
        active_tasks[task["id"]] = task
        try:
            await start_encode(client, task)
        except Exception as e:
            logger.error(e)
        active_tasks.pop(task["id"], None)
        try:
            queue_list.remove(task)
        except:
            pass
        encode_queue.task_done()


# ================= ENCODE COMMAND =================

@Client.on_message((filters.private | filters.group) & filters.command("encode") & filters.reply)
async def encode_cmd(client, message):
    user_id = message.from_user.id
    if not _is_admin_encode(user_id):
        return await message.reply_text("❌ Sirf owner/admin use kar sakta hai.")
    if message.chat.type in ["group", "supergroup"]:
        if not is_authorized_chat(message.chat.id):
            return await message.reply_text("❌ Yeh group authorized nahi hai.")
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to a video or file")
        return
    if not (message.reply_to_message.video or message.reply_to_message.document):
        await message.reply_text("❌ Reply to a downloadable media file")
        return

    rename_wait[user_id] = {
        "msg": message.reply_to_message
    }

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 480p", callback_data="quality|480p"),
            InlineKeyboardButton("📺 720p", callback_data="quality|720p")
        ],
        [
            InlineKeyboardButton("🔥 1080p", callback_data="quality|1080p"),
            InlineKeyboardButton("💎 4K", callback_data="quality|4k")
        ]
    ])

    await message.reply_text(
        "<b>Select Encode Quality</b>",
        reply_markup=buttons
    )
    await start_workers(client)


# ================= QUALITY SELECT =================

@Client.on_callback_query(filters.regex("^quality"))
async def quality_select(client, query):
    _, quality = query.data.split("|")
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Rename", callback_data=f"rename_yes|{quality}"),
            InlineKeyboardButton("No Rename", callback_data=f"rename_no|{quality}")
        ]
    ])
    await query.message.edit_text("Rename file?", reply_markup=buttons)


# ================= RENAME YES =================

@Client.on_callback_query(filters.regex("^rename_yes"))
async def rename_yes(client, query):
    _, quality = query.data.split("|")
    user_id = query.from_user.id
    data = rename_wait.get(user_id)

    if not data or "msg" not in data:
        await query.answer("Session expired. Please send /encode again.", show_alert=True)
        return

    rename_wait[user_id] = {
        "quality": quality,
        "msg": data["msg"],
        "waiting_rename": True
    }
    await query.message.edit_text("Send new file name\nExample: Episode 10")

# ================= GET RENAME =================

@Client.on_message(
    (filters.private | filters.group) &
    filters.text &
    ~filters.command(["encode","tasks","start","help","setthumb","delthumb","viewthumb",
                      "setcaption","delcaption","seecaption","metadata","delmetadata",
                      "addadmin","removeadmin","adminlist","authgroup","unauthgroup",
                      "authlist","rename","queue","logs","batch","cancelbatch"]),
    group=1
)
async def get_rename(client, message):
    user_id = message.from_user.id
    if user_id not in rename_wait:
        return

    data = rename_wait.get(user_id)
    if not data or not data.get("waiting_rename"):
        return

    rename_wait.pop(user_id)
    quality = data.get("quality")
    msg = data.get("msg")
    rename = message.text

    if not quality or not msg:
        await message.reply_text("❌ Session expired. Please send /encode again.")
        return

    task = {
        "id": int(time.time()*1000),
        "user": user_id,
        "quality": quality,
        "rename": rename,
        "crf": DEFAULT_CRF[quality],
        "msg": msg,
        "name": message.from_user.first_name
    }

    queue_list.append(task)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ ultrafast", callback_data=f"preset|{task['id']}|ultrafast"),
            InlineKeyboardButton("🚀 superfast", callback_data=f"preset|{task['id']}|superfast")
        ],
        [
            InlineKeyboardButton("🔥 veryfast", callback_data=f"preset|{task['id']}|veryfast"),
            InlineKeyboardButton("⚙️ fast", callback_data=f"preset|{task['id']}|fast")
        ],
        [
            InlineKeyboardButton("🐢 medium", callback_data=f"preset|{task['id']}|medium"),
            InlineKeyboardButton("💎 slow", callback_data=f"preset|{task['id']}|slow")
        ]
    ])

    await message.reply_text(
        "⚡ Select Encoding Speed",
        reply_markup=buttons
    )

# ================= RENAME NO =================

@Client.on_callback_query(filters.regex("^rename_no"))
async def rename_no(client, query):
    _, quality = query.data.split("|")
    user_id = query.from_user.id
    msg = rename_wait.get(user_id, {}).get("msg")

    if not msg:
        await query.answer("Media not found", show_alert=True)
        return

    task = {
        "id": int(time.time()*1000),
        "user": user_id,
        "quality": quality,
        "rename": None,
        "crf": DEFAULT_CRF[quality],
        "msg": msg,
        "name": query.from_user.first_name
    }

    queue_list.append(task)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ ultrafast", callback_data=f"preset|{task['id']}|ultrafast"),
            InlineKeyboardButton("🚀 superfast", callback_data=f"preset|{task['id']}|superfast")
        ],
        [
            InlineKeyboardButton("🔥 veryfast", callback_data=f"preset|{task['id']}|veryfast"),
            InlineKeyboardButton("⚙️ fast", callback_data=f"preset|{task['id']}|fast")
        ],
        [
            InlineKeyboardButton("🐢 medium", callback_data=f"preset|{task['id']}|medium"),
            InlineKeyboardButton("💎 slow", callback_data=f"preset|{task['id']}|slow")
        ]
    ])
    await query.message.edit_text("Select Encoding Speed", reply_markup=buttons)


# ================= PRESET SELECT =================

@Client.on_callback_query(filters.regex("^preset"))
async def preset_select(client, query):
    _, task_id, preset = query.data.split("|")
    task_id = int(task_id)

    for task in queue_list:
        if task["id"] == task_id:
            task["preset"] = preset
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Low", callback_data=f"compress|{task_id}|low"),
                    InlineKeyboardButton("🟡 Medium", callback_data=f"compress|{task_id}|medium")
                ],
                [
                    InlineKeyboardButton("🟠 High", callback_data=f"compress|{task_id}|high"),
                    InlineKeyboardButton("🔴 Best", callback_data=f"compress|{task_id}|best")
                ],
                [
                    InlineKeyboardButton("⏭️ Skip Compress", callback_data=f"compress|{task_id}|skip")
                ]
            ])
            await query.message.edit_text(
                "🗜️ Select Compression Level\n\n"
                "🟢 Low — ~10% smaller, best quality\n"
                "🟡 Medium — ~30% smaller, good quality\n"
                "🟠 High — ~50% smaller, decent quality\n"
                "🔴 Best — ~70% smaller, max compression\n"
                "⏭️ Skip — no compression",
                reply_markup=buttons
            )
            return


# ================= COMPRESS SELECT =================

@Client.on_callback_query(filters.regex("^compress"))
async def compress_select(client, query):
    _, task_id, level = query.data.split("|")
    task_id = int(task_id)
    user_id = query.from_user.id

    for task in queue_list:
        if task["id"] == task_id:
            if task["user"] != user_id:
                await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)
                return
            task["compress_level"] = level
            await encode_queue.put(task)
            label = "Skip" if level == "skip" else level.capitalize()
            await query.message.edit_text(
                f"📥 Added to Encode Queue\n\n🎬 {task['quality']} | ⚡ {task['preset']} | 🗜️ {label}"
            )
            return


# ================= TASKS COMMAND =================

@Client.on_message(filters.command("tasks") & (filters.private | filters.group))
async def tasks_cmd(client, message):
    user_id = message.from_user.id
    if not _is_admin_encode(user_id):
        return

    if not queue_list and not active_tasks:
        await message.reply_text("📭 Queue khali hai, koi task nahi chal raha.")
        return

    text = "📋 **Encode Queue Status**\n\n"

    if active_tasks:
        text += f"🔄 **Chal raha hai ({len(active_tasks)}):**\n"
        for tid, task in active_tasks.items():
            compress = task.get("compress_level", "skip")
            text += f"  ▶️ `{task['name']}` — {task['quality']} | {task.get('preset', '?')} | 🗜️ {compress}\n"
        text += "\n"

    waiting = [t for t in queue_list if t['id'] not in active_tasks]
    if waiting:
        text += f"⏳ **Wait mein ({len(waiting)}):**\n"
        for i, task in enumerate(waiting, 1):
            compress = task.get("compress_level", "?")
            text += f"  {i}. `{task['name']}` — {task['quality']} | {task.get('preset', '?')} | 🗜️ {compress}\n"

    await message.reply_text(text)


# ================= CANCEL =================

@Client.on_callback_query(filters.regex("^cancel"))
async def cancel_task_encode(client, query):
    parts = query.data.split("|")
    if len(parts) != 3:
        return await query.answer("Invalid cancel data", show_alert=True)

    _, task_id, owner_id = parts
    task_id = int(task_id)
    owner_id = int(owner_id)
    caller_id = query.from_user.id

    # Sirf task ka owner ya admin cancel kar sake
    if caller_id != owner_id and not _is_admin_encode(caller_id):
        return await query.answer("❌ Ye tumhara task nahi hai!", show_alert=True)

    cancel_tasks[task_id] = True
    await query.answer("✅ Cancel request bheja gaya")


# ================= ENCODING =================

async def start_encode(client, task):

    msg = task["msg"]
    user_id = task["user"]
    quality = task["quality"]
    preset = task.get("preset", "veryfast")
    rename = task["rename"]
    crf = task["crf"]

    scale = RESOLUTIONS[quality]

    download = f"temp_{task['id']}.mkv"
    encoded = f"enc_{task['id']}.mkv"

    cancel_tasks[task['id']] = False

    # ---------------- DOWNLOAD ----------------

    progress_msg = await msg.reply_text(
        "📥 Downloading...",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
        )
    )

    start_time = time.time()

    logger.info(f"[{task['id']}] Download started for user {user_id}")
    file_path = await client.download_media(
        msg,
        file_name=download,
        progress=progress_for_pyrogram,
        progress_args=("📥 Downloading...", progress_msg, start_time, f"cancel|{task['id']}|{user_id}")
    )

    logger.info(f"[{task['id']}] Download complete: {file_path}")

    if cancel_tasks.get(task['id']):
        await progress_msg.edit("❌ Download Cancelled")
        return

    # ---------------- ENCODE ----------------

    await progress_msg.edit(
        "⚙️ Encoding...\n\n⬡⬡⬡⬡⬡⬡⬡⬡⬡⬡ 0%",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
        )
    )

    cmd = [
        "ffmpeg",
        "-progress", "pipe:1",
        "-nostats",
        "-i", file_path,
        "-map", "0",
        "-vf", f"scale={scale}:flags=lanczos",
        "-c:v", "libx265",
        "-preset", preset,
        "-crf", str(crf),
        "-x265-params", "log-level=error:me=star:subme=4:ref=4:aq-mode=3:deblock=-1,-1",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-c:s", "copy",
        "-tag:v", "hvc1",
        "-y",
        encoded
    ]

    logger.info(f"[{task['id']}] Encode started | quality={quality} preset={preset} crf={crf}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # stderr ko background mein drain karo — warna buffer full hoke hang hoga
    async def drain_stderr(proc):
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
        except:
            pass

    asyncio.create_task(drain_stderr(process))

    progress = 0
    last_edit_time = 0
    encode_start = time.time()
    patience_index = 0

    while True:

        if cancel_tasks.get(task['id']):
            process.kill()
            await progress_msg.edit("❌ Encode Cancelled")
            return

        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
        except asyncio.TimeoutError:
            logger.warning(f"[{task['id']}] Stdout readline timeout — breaking")
            break

        if not line:
            break

        text = line.decode("utf-8")

        if "out_time=" in text:

            progress = min(progress + 2, 100)
            now = time.time()
            elapsed = int(now - encode_start)

            if now - last_edit_time >= 15:
                last_edit_time = now
                filled = "⬢" * (progress // 10)
                empty = "⬡" * (10 - progress // 10)

                # 45 sec se zyada ho toh patience message dikhao
                if elapsed > 45:
                    patience = PATIENCE_MSGS[patience_index % len(PATIENCE_MSGS)]
                    patience_index += 1
                    status_text = (
                        f"⚙️ Encoding...\n\n{filled}{empty} {progress}%\n\n{patience}"
                    )
                else:
                    status_text = f"⚙️ Encoding...\n\n{filled}{empty} {progress}%"

                try:
                    await progress_msg.edit(
                        status_text,
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
                        )
                    )
                except FloodWait as e:
                    last_edit_time = time.time() + e.value
                except:
                    pass

    # stderr already drained via drain_stderr task
    # wait_for prevents indefinite hang
    try:
        await asyncio.wait_for(process.wait(), timeout=120)
    except asyncio.TimeoutError:
        logger.warning(f"[{task['id']}] Encode wait timeout, killing")
        process.kill()
    logger.info(f"[{task['id']}] Encode complete")

    try:
        await progress_msg.edit("⚙️ Encoding...\n\n⬢⬢⬢⬢⬢⬢⬢⬢⬢⬢ 100% ✅")
    except:
        pass

    # ---------------- RENAME ----------------
    if rename:
        name = f"{rename}.mkv"
    else:
        if msg.document and msg.document.file_name:
            name = msg.document.file_name
        elif msg.video and msg.video.file_name:
            name = msg.video.file_name
        else:
            name = f"encoded_{task['id']}.mkv"

    name = os.path.splitext(name)[0] + ".mkv"

    os.rename(encoded, name)

    # ---------------- METADATA ----------------
    title = await codeflixbots.get_title(user_id) or ""
    author = await codeflixbots.get_author(user_id) or ""
    artist = await codeflixbots.get_artist(user_id) or ""

    meta_file = f"meta_{task['id']}.mkv"

    meta_cmd = [
        "ffmpeg",
        "-i", name,
        "-map", "0",
        "-c", "copy",
        "-metadata", f"title={title}",
        "-metadata", f"author={author}",
        "-metadata", f"artist={artist}",
        "-metadata", "encoder=SharkToonsIndia",
        "-y",
        meta_file
    ]

    logger.info(f"[{task['id']}] Adding metadata")
    await progress_msg.edit("🗜️ Adding Metadata...")

    meta_process = await asyncio.create_subprocess_exec(
        *meta_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        await asyncio.wait_for(meta_process.wait(), timeout=60)
    except asyncio.TimeoutError:
        meta_process.kill()

    os.remove(name)
    os.rename(meta_file, name)

    # ---------------- COMPRESS ----------------
    compress_level = task.get("compress_level", "skip")

    if compress_level != "skip":
        crf_add = COMPRESS_LEVELS[compress_level]["crf_add"]
        compress_crf = min(crf + crf_add, 35)
        compress_file = f"compressed_{task['id']}.mkv"

        logger.info(f"[{task['id']}] Compress started | level={compress_level} crf={compress_crf}")
        await progress_msg.edit(
            f"🗜️ Compressing... [{compress_level.upper()}]\n\n⬡⬡⬡⬡⬡⬡⬡⬡⬡⬡ 0%",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
            )
        )

        compress_cmd = [
            "ffmpeg",
            "-progress", "pipe:1",
            "-nostats",
            "-i", name,
            "-map", "0",
            "-c:v", "libx265",
            "-preset", "veryfast",
            "-crf", str(compress_crf),
            "-x265-params", "log-level=error",
            "-c:a", "copy",
            "-c:s", "copy",
            "-y",
            compress_file
        ]

        compress_process = await asyncio.create_subprocess_exec(
            *compress_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        asyncio.create_task(drain_stderr(compress_process))

        comp_progress = 0
        last_comp_edit = 0
        comp_start = time.time()
        comp_patience_index = 0

        while True:
            if cancel_tasks.get(task['id']):
                compress_process.kill()
                await progress_msg.edit("❌ Compress Cancelled")
                for f in [file_path, name, compress_file, thumb]:
                    try:
                        if f and os.path.exists(f):
                            os.remove(f)
                    except:
                        pass
                return

            try:
                line = await asyncio.wait_for(compress_process.stdout.readline(), timeout=60)
            except asyncio.TimeoutError:
                logger.warning(f"[{task['id']}] Compress stdout timeout — breaking")
                break

            if not line:
                break

            text = line.decode("utf-8")
            if "out_time=" in text:
                comp_progress = min(comp_progress + 2, 100)
                now = time.time()
                elapsed = int(now - comp_start)

                if now - last_comp_edit >= 15:
                    last_comp_edit = now
                    filled = "⬢" * (comp_progress // 10)
                    empty = "⬡" * (10 - comp_progress // 10)

                    if elapsed > 45:
                        patience = PATIENCE_MSGS[comp_patience_index % len(PATIENCE_MSGS)]
                        comp_patience_index += 1
                        status_text = (
                            f"🗜️ Compressing... [{compress_level.upper()}]\n\n"
                            f"{filled}{empty} {comp_progress}%\n\n{patience}"
                        )
                    else:
                        status_text = f"🗜️ Compressing... [{compress_level.upper()}]\n\n{filled}{empty} {comp_progress}%"

                    try:
                        await progress_msg.edit(
                            status_text,
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
                            )
                        )
                    except FloodWait as e:
                        last_comp_edit = time.time() + e.value
                    except:
                        pass

        try:
            await asyncio.wait_for(compress_process.wait(), timeout=120)
        except asyncio.TimeoutError:
            logger.warning(f"[{task['id']}] Compress wait timeout, killing")
            compress_process.kill()

        try:
            await progress_msg.edit(f"🗜️ Compressing... [{compress_level.upper()}]\n\n⬢⬢⬢⬢⬢⬢⬢⬢⬢⬢ 100% ✅")
        except:
            pass

        if os.path.exists(compress_file):
            os.remove(name)
            os.rename(compress_file, name)
            logger.info(f"[{task['id']}] Compress complete")
        else:
            logger.warning(f"[{task['id']}] Compress failed, using encoded file")
    else:
        logger.info(f"[{task['id']}] Compress skipped")

    # ---------------- THUMB ----------------
    thumb = None
    thumb_id = await codeflixbots.get_thumbnail(user_id)

    if thumb_id:
        try:
            thumb = await client.download_media(
                thumb_id,
                file_name=f"thumb_{task['id']}.jpg"
            )
        except:
            thumb = None

    logger.info(f"[{task['id']}] Upload started")
    # ---------------- UPLOAD ----------------
    await progress_msg.edit(
        "📤 Uploading...",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task['id']}|{user_id}")]]
        )
    )

    while True:

        if cancel_tasks.get(task['id']):
            await progress_msg.edit("❌ Upload Cancelled")
            return

        try:

            start_time = time.time()

            await client.send_document(
                chat_id=user_id,
                document=name,
                caption=name,
                thumb=thumb if thumb else None,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading...", progress_msg, start_time, f"cancel|{task['id']}|{user_id}")
            )

            break

        except FloodWait as e:
            await asyncio.sleep(e.value)

    logger.info(f"[{task['id']}] Task complete, cleaning up")
    # ---------------- CLEANUP ----------------
    await progress_msg.delete()
    for f in [file_path, name, thumb]:
        try:
            if f and os.path.exists(f):
                os.remove(f)
        except:
            pass
