import asyncio
import sys
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from helper.permissions import is_admin as _perm_is_admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ================= ADMIN CHECK =================

def is_admin(user_id):
    return user_id == Config.OWNER_ID or _perm_is_admin(user_id)

# ================= SAFE IMPORTS =================
# Dusre plugins ke active_tasks dicts import karo
# Try/except — agar koi plugin nahi hai toh crash nahi hoga

def get_encode_tasks():
    try:
        from plugins.encode import active_tasks, encode_queue
        return active_tasks, encode_queue.qsize()
    except:
        return {}, 0

def get_compress_tasks():
    try:
        from plugins.compress import active_tasks, compress_queue
        return active_tasks, compress_queue.qsize()
    except:
        return {}, 0

def get_merge_tasks():
    try:
        from plugins.merge import active_tasks, merge_queue, merge_sessions
        return active_tasks, merge_queue.qsize(), merge_sessions
    except:
        return {}, 0, {}

def get_upscale_tasks():
    try:
        from plugins.upscale import cancel_upscale, upscale_wait
        # Active = jo cancel_upscale mein False hain (running)
        active = {k: v for k, v in cancel_upscale.items() if v is False}
        return active, upscale_wait
    except:
        return {}, {}

def get_rename_queue():
    try:
        from plugins.file_rename import file_queue, current_user, queue_users
        return file_queue.qsize(), current_user, queue_users
    except:
        return 0, None, {}

# ================= /status COMMAND =================

@Client.on_message(
    (filters.private | filters.group) &
    filters.command("status")
)
async def status_cmd(client, message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.reply_text("❌ Sirf owner aur admins use kar sakte hain")
        return

    encode_tasks, encode_queue_size     = get_encode_tasks()
    compress_tasks, compress_queue_size = get_compress_tasks()
    merge_tasks, merge_queue_size, merge_sessions = get_merge_tasks()
    upscale_active, upscale_wait        = get_upscale_tasks()
    rename_size, rename_current, rename_users = get_rename_queue()

    # Check karo kuch chal raha hai
    total_active = (
        len(encode_tasks) +
        len(compress_tasks) +
        len(merge_tasks) +
        len(upscale_active) +
        rename_size
    )

    lines = []
    lines.append("╔══════════════════════════╗")
    lines.append("║      🤖  BOT  STATUS       ║")
    lines.append("╚══════════════════════════╝")
    lines.append("")

    # -------- ENCODE --------
    lines.append("🎬  **ENCODE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if encode_tasks:
        for tid, task in encode_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📊 {task.get('quality','?')} · {task.get('preset','?')} · CRF {task.get('crf','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if encode_queue_size:
        lines.append(f"  📦 Queue: `{encode_queue_size}` pending")
    lines.append("")

    # -------- COMPRESS --------
    lines.append("🗜️  **COMPRESS**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if compress_tasks:
        for tid, task in compress_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📊 {task.get('label', task.get('level','?'))} · CRF {task.get('crf','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if compress_queue_size:
        lines.append(f"  📦 Queue: `{compress_queue_size}` pending")
    lines.append("")

    # -------- MERGE --------
    lines.append("🔀  **MERGE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if merge_tasks:
        for tid, task in merge_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📦 Files: `{len(task.get('files',[]))}`\n"
                f"  📊 {task.get('quality_info',{}).get('label','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if merge_sessions:
        lines.append(f"  🕐 Sessions: `{len(merge_sessions)}` collecting files")
    if merge_queue_size:
        lines.append(f"  📦 Queue: `{merge_queue_size}` pending")
    lines.append("")

    # -------- UPSCALE --------
    lines.append("🔍  **UPSCALE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if upscale_active:
        lines.append(f"  ⚙️ Running: `{len(upscale_active)}` task(s)")
    else:
        lines.append("  ✅ Koi task nahi")
    if upscale_wait:
        lines.append(f"  🕐 Waiting: `{len(upscale_wait)}` user(s)")
    lines.append("")

    # -------- RENAME --------
    lines.append("✏️  **RENAME**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if rename_current:
        lines.append(f"  ⚙️ Processing: `{rename_current}`")
    if rename_users:
        for user, count in rename_users.items():
            lines.append(f"  👤 `{user}` — {count} file(s)")
    if rename_size:
        lines.append(f"  📦 Queue: `{rename_size}` pending")
    if not rename_current and not rename_users:
        lines.append("  ✅ Koi task nahi")
    lines.append("")

    # -------- SUMMARY --------
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if total_active == 0:
        lines.append("💤 **Bot bilkul free hai!**")
    else:
        lines.append(f"📊 **Total active: `{total_active}` task(s)**")

    text = "\n".join(lines)

    # Refresh button
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"status_refresh|{user_id}")]
    ])

    await message.reply_text(text, reply_markup=buttons)


# ================= REFRESH BUTTON =================

@Client.on_callback_query(filters.regex("^status_refresh"))
async def status_refresh(client, query):
    _, user_id = query.data.split("|")
    user_id = int(user_id)

    if query.from_user.id != user_id:
        await query.answer("❌ Ye tumhara status nahi hai!", show_alert=True)
        return

    encode_tasks, encode_queue_size     = get_encode_tasks()
    compress_tasks, compress_queue_size = get_compress_tasks()
    merge_tasks, merge_queue_size, merge_sessions = get_merge_tasks()
    upscale_active, upscale_wait        = get_upscale_tasks()
    rename_size, rename_current, rename_users = get_rename_queue()

    total_active = (
        len(encode_tasks) +
        len(compress_tasks) +
        len(merge_tasks) +
        len(upscale_active) +
        rename_size
    )

    lines = []
    lines.append("╔══════════════════════════╗")
    lines.append("║      🤖  BOT  STATUS       ║")
    lines.append("╚══════════════════════════╝")
    lines.append("")

    lines.append("🎬  **ENCODE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if encode_tasks:
        for tid, task in encode_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📊 {task.get('quality','?')} · {task.get('preset','?')} · CRF {task.get('crf','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if encode_queue_size:
        lines.append(f"  📦 Queue: `{encode_queue_size}` pending")
    lines.append("")

    lines.append("🗜️  **COMPRESS**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if compress_tasks:
        for tid, task in compress_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📊 {task.get('label', task.get('level','?'))} · CRF {task.get('crf','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if compress_queue_size:
        lines.append(f"  📦 Queue: `{compress_queue_size}` pending")
    lines.append("")

    lines.append("🔀  **MERGE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if merge_tasks:
        for tid, task in merge_tasks.items():
            lines.append(
                f"  ⚙️ Running\n"
                f"  👤 `{task.get('name', task.get('user', '?'))}`\n"
                f"  📦 Files: `{len(task.get('files',[]))}`\n"
                f"  📊 {task.get('quality_info',{}).get('label','?')}"
            )
    else:
        lines.append("  ✅ Koi task nahi")
    if merge_sessions:
        lines.append(f"  🕐 Sessions: `{len(merge_sessions)}` collecting files")
    if merge_queue_size:
        lines.append(f"  📦 Queue: `{merge_queue_size}` pending")
    lines.append("")

    lines.append("🔍  **UPSCALE**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if upscale_active:
        lines.append(f"  ⚙️ Running: `{len(upscale_active)}` task(s)")
    else:
        lines.append("  ✅ Koi task nahi")
    if upscale_wait:
        lines.append(f"  🕐 Waiting: `{len(upscale_wait)}` user(s)")
    lines.append("")

    lines.append("✏️  **RENAME**")
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    if rename_current:
        lines.append(f"  ⚙️ Processing: `{rename_current}`")
    if rename_users:
        for user, count in rename_users.items():
            lines.append(f"  👤 `{user}` — {count} file(s)")
    if rename_size:
        lines.append(f"  📦 Queue: `{rename_size}` pending")
    if not rename_current and not rename_users:
        lines.append("  ✅ Koi task nahi")
    lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if total_active == 0:
        lines.append("💤 **Bot bilkul free hai!**")
    else:
        lines.append(f"📊 **Total active: `{total_active}` task(s)**")

    text = "\n".join(lines)

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"status_refresh|{user_id}")]
    ])

    try:
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer("✅ Refreshed!")
    except:
        await query.answer("Already up to date")
