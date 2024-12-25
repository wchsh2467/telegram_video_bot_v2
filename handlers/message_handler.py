import logging
from pyrogram import Client, filters
from pyrogram.types import Message

from services.user_service import UserService
from services.video_service import VideoService

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, app: Client, user_service: UserService, video_service: VideoService):
        self.app = app
        self.user_service = user_service
        self.video_service = video_service
        self._register_handlers()
        
    def _register_handlers(self):
        """רישום כל המטפלים בהודעות"""
        
        @self.app.on_message(filters.private & (filters.video | filters.document))
        async def handle_video(client: Client, message: Message):
            """טיפול בקבצי וידאו"""
            logger.info(f"התקבלה הודעת וידאו/מסמך מ: {message.from_user.id}")
            
            user_id = message.from_user.id
            
            # בדיקת הרשאות
            if not self.user_service.is_user_allowed(user_id):
                logger.warning(f"משתמש לא מורשה {user_id} ניסה להשתמש בבוט")
                await message.reply_text(
                    "**📛 אין לך הרשאה להשתמש בבוט זה**\n"
                    "אנא פנה למנהל המערכת"
                )
                return
                
            # בדיקה שזה אכן קובץ וידאו
            if message.document:
                logger.info(f"סוג המסמך: {message.document.mime_type}")
                if not (message.document.mime_type and message.document.mime_type.startswith("video/")):
                    await message.reply_text("❌ אנא שלח קובץ וידאו בלבד")
                    return
                
            # הוספה לתור העיבוד
            await self.video_service.add_to_queue(message)
            logger.info(f"התקבל וידאו חדש ממשתמש {user_id}")
            await message.reply_text("✅ הקובץ התקבל ומעובד...")
            
        @self.app.on_message(filters.private & filters.text & ~filters.command)
        async def handle_text(client: Client, message: Message):
            """טיפול בהודעות טקסט"""
            logger.info(f"התקבלה הודעת טקסט מ: {message.from_user.id}")
            await message.reply_text(
                "🎥 אנא שלח קובץ וידאו לניתוח\n\n"
                "לעזרה נוספת, השתמש בפקודה /help"
            )
