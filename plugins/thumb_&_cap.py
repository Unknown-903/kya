from pyrogram import Client, filters
from helper.database import codeflixbots
from helper.auth import auth_chats


# ================= SET CAPTION ================= #

@Client.on_message((filters.private | filters.group) & filters.command("set_caption"))
async def add_caption(client, message):

    if message.chat.type in ["group","supergroup"]:
        if message.chat.id not in auth_chats:
            return

    if len(message.command) == 1:
        return await message.reply_text(
            "**Give the caption format**\n\n"
            "**Example:**\n"
            "`/set_caption 📕 Name ➠ {filename}\n\n📦 Size ➠ {filesize}\n\n⏰ Duration ➠ {duration}`"
        )

    caption = message.text.split(" ", 1)[1]

    await codeflixbots.set_caption(message.from_user.id, caption=caption)

    await message.reply_text("✅ **Caption saved successfully**")


# ================= DELETE CAPTION ================= #

@Client.on_message((filters.private | filters.group) & filters.command("del_caption"))
async def delete_caption(client, message):

    caption = await codeflixbots.get_caption(message.from_user.id)

    if not caption:
        return await message.reply_text("❌ You don't have any caption")

    await codeflixbots.set_caption(message.from_user.id, caption=None)

    await message.reply_text("🗑 **Caption deleted successfully**")


# ================= VIEW CAPTION ================= #

@Client.on_message((filters.private | filters.group) & filters.command(["see_caption","view_caption"]))
async def see_caption(client, message):

    caption = await codeflixbots.get_caption(message.from_user.id)

    if caption:
        await message.reply_text(f"**Your Caption:**\n\n`{caption}`")
    else:
        await message.reply_text("❌ You don't have any caption")


# ================= SET THUMB ================= #

@Client.on_message((filters.private | filters.group) & filters.command("setthumb") & filters.reply)
async def set_thumb(client, message):

    if message.chat.type in ["group","supergroup"]:
        if message.chat.id not in auth_chats:
            return

    reply = message.reply_to_message

    if not reply.photo:
        return await message.reply_text("❌ Reply to a photo to set thumbnail")

    user_id = message.from_user.id

    file_id = reply.photo.file_id

    await codeflixbots.set_thumbnail(user_id, file_id)

    await message.reply_text("✅ **Thumbnail saved successfully**")


# ================= VIEW THUMB ================= #

@Client.on_message((filters.private | filters.group) & filters.command(["view_thumb","viewthumb"]))
async def viewthumb(client, message):

    thumb = await codeflixbots.get_thumbnail(message.from_user.id)

    if thumb:
        await client.send_photo(chat_id=message.chat.id, photo=thumb)
    else:
        await message.reply_text("❌ You don't have any thumbnail")


# ================= DELETE THUMB ================= #

@Client.on_message((filters.private | filters.group) & filters.command(["del_thumb","delthumb"]))
async def removethumb(client, message):

    thumb = await codeflixbots.get_thumbnail(message.from_user.id)

    if not thumb:
        return await message.reply_text("❌ You don't have any thumbnail")

    await codeflixbots.set_thumbnail(message.from_user.id, None)

    await message.reply_text("🗑 **Thumbnail deleted successfully**")
