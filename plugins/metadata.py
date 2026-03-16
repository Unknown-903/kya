from helper.database import codeflixbots as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery


# ===========================
# VIEW METADATA
# ===========================

@Client.on_message(filters.command("metadata") & (filters.private | filters.group))
async def view_metadata(client, message):

    user_id = message.from_user.id

    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)

    text = f"""
**Your Current Metadata**

Title : `{title or 'Not Set'}`
Author : `{author or 'Not Set'}`
Artist : `{artist or 'Not Set'}`
Video : `{video or 'Not Set'}`
Audio : `{', '.join(audio) if audio else 'Not Set'}`
Subtitle : `{', '.join(subtitle) if subtitle else 'Not Set'}`
"""

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🗑 Delete Metadata", callback_data="del_metadata")]]
    )

    await message.reply_text(text, reply_markup=buttons)


# ===========================
# SET METADATA
# ===========================

@Client.on_message(filters.command("setmetadata") & (filters.private | filters.group))
async def setmetadata(client, message):

    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:**\n"
            "`/setmetadata Name`\n\n"
            "**Example:**\n"
            "`/setmetadata Netflix`"
        )

    name = message.text.split(" ", 1)[1].strip()
    user_id = message.from_user.id

    await db.set_title(user_id, name)
    await db.set_author(user_id, name)
    await db.set_artist(user_id, name)
    await db.set_video(user_id, name)
    await db.set_audio(user_id, [name])
    await db.set_subtitle(user_id, [name])
    await db.set_metadata(user_id, "On")

    await message.reply_text(
        f"✅ **Metadata Set Successfully**\n\n"
        f"All metadata fields now use:\n`{name}`"
    )


# ===========================
# DELETE METADATA
# ===========================

@Client.on_callback_query(filters.regex("del_metadata"))
async def delete_metadata(client, query: CallbackQuery):

    user_id = query.from_user.id

    await db.set_title(user_id, "")
    await db.set_author(user_id, "")
    await db.set_artist(user_id, "")
    await db.set_video(user_id, "")
    await db.set_audio(user_id, [])
    await db.set_subtitle(user_id, [])
    await db.set_metadata(user_id, "Off")

    await query.message.edit_text("🗑 Metadata Deleted Successfully")
