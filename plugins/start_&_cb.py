import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import Config, Txt


# ================= START =================

@Client.on_message(filters.command("start"))
async def start(client, message: Message):

    if message.chat.type in ["group", "supergroup"]:
        return await message.reply_text(
            "👋 **Hello!**\n\n"
            "Use me in **private chat** to rename files.\n\n"
            f"👉 https://t.me/{(await client.get_me()).username}"
        )

    user = message.from_user
    await codeflixbots.add_user(client, message)

    m = await message.reply_text("ʜᴇʜᴇ..ɪ'ᴍ ᴀɴʏᴀ!\nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ. . .")
    await asyncio.sleep(0.4)
    await m.edit_text("🎊")
    await asyncio.sleep(0.5)
    await m.edit_text("⚡")
    await asyncio.sleep(0.5)
    await m.edit_text("ᴡᴀᴋᴜ ᴡᴀᴋᴜ!...")
    await asyncio.sleep(0.4)
    await m.delete()

    await message.reply_sticker(
        "CAACAgUAAxkBAAECroBmQKMAAQ-Gw4nibWoj_pJou2vP1a4AAlQIAAIzDxlVkNBkTEb1Lc4eBA"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help")],
        [
            InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇs", url="https://t.me/Codeflix_Bots"),
            InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ •", url="https://t.me/CodeflixSupport")
        ],
        [
            InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
            InlineKeyboardButton("sᴏᴜʀᴄᴇ •", callback_data="source")
        ]
    ])

    if Config.START_PIC:
        await message.reply_photo(
            Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )


# ================= CALLBACK HANDLER =================

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):

    data = query.data
    user_id = query.from_user.id

    if data == "home":

        await query.message.edit_text(
            Txt.START_TXT.format(query.from_user.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help")],
                [
                    InlineKeyboardButton("• ᴜᴘᴅᴀᴛᴇs", url="https://t.me/Codeflix_Bots"),
                    InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ •", url="https://t.me/CodeflixSupport")
                ],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton("sᴏᴜʀᴄᴇ •", callback_data="source")
                ]
            ])
        )


    elif data == "help":

        bot = await client.get_me()

        await query.message.edit_text(
            Txt.HELP_TXT.format(bot.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data="file_names")],
                [
                    InlineKeyboardButton("• ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
                    InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ •", callback_data="caption")
                ],
                [
                    InlineKeyboardButton("• ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta"),
                    InlineKeyboardButton("ᴅᴏɴᴀᴛᴇ •", callback_data="donate")
                ],
                [InlineKeyboardButton("• ʜᴏᴍᴇ", callback_data="home")]
            ])
        )


    elif data == "caption":

        await query.message.edit_text(
            Txt.CAPTION_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )


    elif data == "file_names":

        format_template = await codeflixbots.get_format_template(user_id)

        await query.message.edit_text(
            Txt.FILE_NAME_TXT.format(format_template=format_template),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )


    elif data == "thumbnail":

        await query.message.edit_text(
            Txt.THUMBNAIL_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )


    elif data == "meta":

        await query.message.edit_text(
            Txt.SEND_METADATA,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )


    elif data == "donate":

        await query.message.edit_text(
            Txt.DONATE_TXT,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help"),
                    InlineKeyboardButton("ᴏᴡɴᴇʀ", url="https://t.me/sewxiy")
                ]
            ])
        )


    elif data == "about":

        await query.message.edit_text(
            Txt.ABOUT_TXT,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url="https://t.me/CodeflixSupport"),
                    InlineKeyboardButton("ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help")
                ],
                [
                    InlineKeyboardButton("• ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/cosmic_freak"),
                    InlineKeyboardButton("ɴᴇᴛᴡᴏʀᴋ •", url="https://t.me/otakuflix_network")
                ],
                [InlineKeyboardButton("• ʜᴏᴍᴇ •", callback_data="home")]
            ])
        )


    elif data == "source":

        await query.message.edit_text(
            Txt.SOURCE_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʜᴏᴍᴇ •", callback_data="home")]
            ])
        )


    elif data == "close":

        try:
            await query.message.delete()
        except:
            pass


# ================= HELP COMMAND =================

@Client.on_message(filters.command("help"))
async def help_command(client, message):

    bot = await client.get_me()

    await message.reply_text(
        Txt.HELP_TXT.format(bot.mention),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data="file_names")],
            [
                InlineKeyboardButton("• ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
                InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ •", callback_data="caption")
            ],
            [
                InlineKeyboardButton("• ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta"),
                InlineKeyboardButton("ᴅᴏɴᴀᴛᴇ •", callback_data="donate")
            ],
            [InlineKeyboardButton("• ʜᴏᴍᴇ", callback_data="home")]
        ])
    )
