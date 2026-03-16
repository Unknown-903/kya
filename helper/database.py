import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from .utils import send_log

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, uri: str, db_name: str):

        self._client = AsyncIOMotorClient(uri)

        self.db = self._client[db_name]
        self.col = self.db.user

        logger.info(f"MongoDB Connected → {db_name}")


# ================= USER TEMPLATE =================

    def new_user(self, user_id: int):

        today = datetime.date.today().isoformat()

        return {

            "_id": int(user_id),

            "join_date": today,

            "file_id": None,
            "caption": None,

            "metadata": True,
            "metadata_code": "Telegram : @SharkToonsIndia",

            "format_template": None,
            "media_type": "document",

            "title": "Encoded by @SharkToonsIndia",
            "author": "@SharkToonsIndia",
            "artist": "@SharkToonsIndia",

            "audio": [
                "Japanese Audio|jpn",
                "English Audio|eng",
                "Hindi Audio|hin",
                "Tamil Audio|tam",
                "Telugu Audio|tel"
            ],

            "subtitle": [
                "English Subtitles|eng"
            ],

            "video": "Encoded By @SharkToonsIndia",

            "ban_status": {

                "is_banned": False,
                "ban_duration": 0,
                "banned_on": datetime.date.max.isoformat(),
                "ban_reason": ""
            }
        }


# ================= USER MANAGEMENT =================

    async def add_user(self, bot, message):

        user = message.from_user

        if not await self.is_user_exist(user.id):

            try:

                await self.col.insert_one(self.new_user(user.id))

                await send_log(bot, user)

                logger.info(f"New user added → {user.id}")

            except Exception as e:

                logger.error(e)


    async def is_user_exist(self, user_id: int):

        user = await self.col.find_one({"_id": int(user_id)})

        return bool(user)


    async def total_users_count(self):

        return await self.col.count_documents({})


    async def get_all_users(self):

        return self.col.find({})


    async def delete_user(self, user_id: int):

        await self.col.delete_many({"_id": int(user_id)})


# ================= GENERIC SET / GET =================

    async def _set(self, user_id, key, value):

        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {key: value}}
        )


    async def _get(self, user_id, key, default=None):

        user = await self.col.find_one({"_id": int(user_id)})

        if user:

            return user.get(key, default)

        return default


# ================= THUMBNAIL =================

    async def set_thumbnail(self, user_id, file_id):

        await self._set(user_id, "file_id", file_id)


    async def get_thumbnail(self, user_id):

        return await self._get(user_id, "file_id")


# ================= CAPTION =================

    async def set_caption(self, user_id, caption):

        await self._set(user_id, "caption", caption)


    async def get_caption(self, user_id):

        return await self._get(user_id, "caption")


# ================= RENAME TEMPLATE =================

    async def set_format_template(self, user_id, template):

        await self._set(user_id, "format_template", template)


    async def get_format_template(self, user_id):

        return await self._get(user_id, "format_template")


# ================= MEDIA TYPE =================

    async def set_media_preference(self, user_id, media_type):

        await self._set(user_id, "media_type", media_type)


    async def get_media_preference(self, user_id):

        return await self._get(user_id, "media_type", "document")


# ================= METADATA =================

    async def set_metadata(self, user_id, metadata):

        await self._set(user_id, "metadata", metadata)


    async def get_metadata(self, user_id):

        return await self._get(user_id, "metadata", True)


# ================= TITLE =================

    async def get_title(self, user_id):

        return await self._get(user_id, "title")


    async def set_title(self, user_id, title):

        await self._set(user_id, "title", title)


# ================= AUTHOR =================

    async def get_author(self, user_id):

        return await self._get(user_id, "author")


    async def set_author(self, user_id, author):

        await self._set(user_id, "author", author)


# ================= ARTIST =================

    async def get_artist(self, user_id):

        return await self._get(user_id, "artist")


    async def set_artist(self, user_id, artist):

        await self._set(user_id, "artist", artist)


# ================= AUDIO =================

    async def get_audio(self, user_id):

        return await self._get(user_id, "audio", [])


    async def set_audio(self, user_id, audio_list):

        if not isinstance(audio_list, list):

            audio_list = [audio_list]

        await self._set(user_id, "audio", audio_list)


# ================= SUBTITLE =================

    async def get_subtitle(self, user_id):

        return await self._get(user_id, "subtitle", [])


    async def set_subtitle(self, user_id, subtitle_list):

        if not isinstance(subtitle_list, list):

            subtitle_list = [subtitle_list]

        await self._set(user_id, "subtitle", subtitle_list)


# ================= VIDEO =================

    async def get_video(self, user_id):

        return await self._get(user_id, "video")


    async def set_video(self, user_id, video):

        await self._set(user_id, "video", video)


# ================= DATABASE INSTANCE =================

codeflixbots = Database(Config.DB_URL, Config.DB_NAME)
