from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from helper.database import codeflixbots
from helper.auth import auth_chats
from helper.permissions import is_authorized_chat


# ================= AUTORENAME =================

@Client.on_message((filters.private | filters.group) & filters.command("autorename"))
async def auto_rename_command(client, message):

    # Group authorization check
    if message.chat.type in ["group", "supergroup"]:
        if not is_authorized_chat(message.chat.id):
            return await message.reply_text(
                "❌ This group is not authorized.\nUse /auth first."
            )

    user_id = message.from_user.id

    # Extract command argument
    command_parts = message.text.split(maxsplit=1)

    if len(command_parts) < 2 or not command_parts[1].strip():
        return await message.reply_text(
            "**⚠️ Please provide a valid rename format after** `/autorename`.\n\n"
            "💡 **Example:**\n"
            "`/autorename Overflow [S{season}E{episode}] - [Dual] {quality}`\n\n"
            "📝 **Available placeholders:**\n"
            "- `{season}` → Season number\n"
            "- `{episode}` → Episode number\n"
            "- `{quality}` → File quality (e.g., 1080p, 720p)"
        )

    format_template = command_parts[1].strip()

    # Save template
    await codeflixbots.set_format_template(user_id, format_template)

    await message.reply_text(
        f"✅ **Rename template saved successfully!**\n\n"
        f"`{format_template}`\n\n"
        "📦 Now send files to rename."
    )


# ================= SET MEDIA TYPE =================

@Client.on_message((filters.private | filters.group) & filters.command("setmedia"))
async def set_media_command(client, message):

    # Group authorization check
    if message.chat.type in ["group", "supergroup"]:
        if not is_authorized_chat(message.chat.id):
            return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Documents", callback_data="setmedia_document")],
        [InlineKeyboardButton("🎬 Videos", callback_data="setmedia_video")],
        [InlineKeyboardButton("🎵 Audio", callback_data="setmedia_audio")],
    ])

    await message.reply_text(
        "🎛 **Choose your default media type for uploads:**\n\n"
        "📜 Document - Send files as documents\n"
        "🎬 Video - Send as playable videos\n"
        "🎵 Audio - Send as audio files\n\n"
        "Tap your choice below ⬇️",
        reply_markup=keyboard,
        quote=True
    )


# ================= HANDLE MEDIA CALLBACK =================

@Client.on_callback_query(filters.regex(r"^setmedia_"))
async def handle_media_selection(client, callback_query: CallbackQuery):

    user_id = callback_query.from_user.id
    media_type = callback_query.data.split("_", 1)[1].capitalize()

    try:
        await codeflixbots.set_media_preference(user_id, media_type.lower())

        await callback_query.answer(f"✅ {media_type} preference saved!")

        await callback_query.message.edit_text(
            f"🎯 **Media Preference Updated!**\n\n"
            f"Your files will now be sent as **{media_type}** ✅\n\n"
            "🚀 Change anytime with `/setmedia`"
        )

    except Exception as e:

        await callback_query.answer("⚠️ Something went wrong!", show_alert=True)

        await callback_query.message.edit_text(
            f"❌ **Error:** Could not save preference.\n"
            f"Details: `{str(e)}`"
        )
