from pyrogram import Client, filters
from helper.auth import auth_chats
from config import Config


def is_owner(user_id):
    return user_id == Config.OWNER_ID


@Client.on_message((filters.private | filters.group) & filters.command("auth"))
async def authorize_group(client, message):

    if not is_owner(message.from_user.id):
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    chat_id = message.chat.id

    if chat_id in auth_chats:
        return await message.reply_text(f"⚠️ Yeh chat already authorized hai\n\n`{chat_id}`")

    auth_chats.add(chat_id)
    await message.reply_text(f"✅ Chat authorized\n\n`{chat_id}`")


@Client.on_message((filters.private | filters.group) & filters.command("rauth"))
async def unauthorize_group(client, message):

    if not is_owner(message.from_user.id):
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    chat_id = message.chat.id

    if chat_id not in auth_chats:
        return await message.reply_text(f"⚠️ Yeh chat authorized nahi hai\n\n`{chat_id}`")

    auth_chats.discard(chat_id)
    await message.reply_text(f"❌ Chat unauthorized kiya\n\n`{chat_id}`")


@Client.on_message((filters.private | filters.group) & filters.command("authlist"))
async def auth_list(client, message):

    if not is_owner(message.from_user.id):
        return await message.reply_text("❌ Sirf owner use kar sakta hai")

    if not auth_chats:
        return await message.reply_text("📋 Koi authorized chat nahi hai")

    text = "📋 **Authorized Chats**\n\n"
    for cid in auth_chats:
        text += f"• `{cid}`\n"

    await message.reply_text(text)
