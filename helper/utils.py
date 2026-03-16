import time
import re
from datetime import datetime
from pytz import timezone
from config import Config, Txt
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait

# ================= PROGRESS BAR =================

last_edit_times = {}  # message_id -> last edit timestamp

async def progress_for_pyrogram(current, total, ud_type, message, start, cancel_data=None):
    now = time.time()
    diff = now - start
    if diff <= 0:
        return

    # Throttle: har 5 seconds mein ek baar edit karo
    msg_id = message.id
    last = last_edit_times.get(msg_id, 0)
    if now - last < 5 and current != total:
        return
    last_edit_times[msg_id] = now

    percentage = current * 100 / total
    speed = current / diff if diff > 0 else 0
    elapsed_time = round(diff) * 1000
    time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
    estimated_total_time = elapsed_time + time_to_completion

    elapsed_time = TimeFormatter(elapsed_time)
    estimated_total_time = TimeFormatter(estimated_total_time)

    filled = "⬢" * int(percentage / 10)
    empty = "⬡" * (10 - int(percentage / 10))
    progress = f"{filled}{empty}"

    text = (
        f"{progress} {round(percentage, 2)}%\n\n"
        f"📦 {humanbytes(current)} / {humanbytes(total)}\n"
        f"⚡ {humanbytes(speed)}/s\n"
        f"⏳ {estimated_total_time if estimated_total_time else '0 s'}"
    )

    # Cancel button — agar cancel_data diya hai toh secure button, warna generic
    if cancel_data:
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=cancel_data)]]
        )
    else:
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="close")]]
        )

    try:
        await message.edit_text(
            f"{ud_type}\n\n{text}",
            reply_markup=markup,
        )
        if current == total:
            last_edit_times.pop(msg_id, None)
    except FloodWait as e:
        last_edit_times[msg_id] = time.time() + e.value
    except:
        pass

# ================= HUMAN BYTES =================

def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    Dic_powerN = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {Dic_powerN[n]}"

# ================= TIME FORMAT =================

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        (str(days) + "d, " if days else "")
        + (str(hours) + "h, " if hours else "")
        + (str(minutes) + "m, " if minutes else "")
        + (str(seconds) + "s, " if seconds else "")
    )
    return tmp[:-2] if tmp else "0s"

# ================= TIME CONVERTER =================

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%d:%02d:%02d" % (hour, minutes, seconds)

# ================= LOG NEW USER =================

async def send_log(b, u):
    if Config.LOG_CHANNEL is None:
        return
    curr = datetime.now(timezone("Asia/Kolkata"))
    date = curr.strftime("%d %B, %Y")
    time_ = curr.strftime("%I:%M:%S %p")
    await b.send_message(
        Config.LOG_CHANNEL,
        f"**--New User Started Bot--**\n\n"
        f"User: {u.mention}\n"
        f"ID: `{u.id}`\n"
        f"Username: @{u.username}\n\n"
        f"Date: {date}\n"
        f"Time: {time_}\n\n"
        f"By: {b.mention}",
    )

# ================= PREFIX SUFFIX =================

def add_prefix_suffix(input_string, prefix="", suffix=""):
    pattern = r"(?P<filename>.*?)(\.\w+)?$"
    match = re.search(pattern, input_string)
    if not match:
        return input_string
    filename = match.group("filename")
    extension = match.group(2) or ""
    if prefix:
        filename = f"{prefix}{filename}"
    if suffix:
        filename = f"{filename} {suffix}"
    return f"{filename}{extension}"
