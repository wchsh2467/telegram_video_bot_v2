import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from services.user_service import UserService

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, app: Client, user_service: UserService):
        self.app = app
        self.user_service = user_service
        self._register_handlers()
        
    def _register_handlers(self):
        """רישום כל הפקודות"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client: Client, message: Message):
            """טיפול בפקודת start"""
            await message.reply_text(
                "👋 שלום! אני בוט שמנתח קבצי וידאו ומספק מידע טכני עליהם.\n\n"
                "🎥 פשוט שלח לי קובץ וידאו ואני אטפל בו עבורך.\n\n"
                "⚡️ תכונות עיקריות:\n"
                "• המרה אוטומטית ל-MP4\n"
                "• זיהוי איכות הווידאו\n"
                "• שמירת קבצים לשימוש חוזר\n"
                "• תמיכה בכל סוגי הווידאו\n\n"
                "📝 פקודות נוספות:\n"
                "/help - הצגת עזרה מפורטת\n"
                "/about - מידע על הבוט"
            )
            
        @self.app.on_message(filters.command("help"))
        async def help_command(client: Client, message: Message):
            """טיפול בפקודת help"""
            await message.reply_text(
                "🔍 **מדריך שימוש**\n\n"
                "1️⃣ **שליחת וידאו**\n"
                "• שלח קובץ וידאו כלשהו\n"
                "• הבוט יעבד אותו אוטומטית\n"
                "• תקבל את הווידאו מעובד עם כל המידע\n\n"
                "2️⃣ **פורמטים נתמכים**\n"
                "• MP4, AVI, MKV, MOV, WMV ועוד\n"
                "• המרה אוטומטית ל-MP4\n\n"
                "3️⃣ **איכויות מזוהות**\n"
                "• 144p עד 4K\n"
                "• CAM, DVDRip, WEB-DL ועוד\n\n"
                "❓ לשאלות נוספות, פנה למנהל המערכת"
            )
            
        @self.app.on_message(filters.command("about"))
        async def about_command(client: Client, message: Message):
            """טיפול בפקודת about"""
            await message.reply_text(
                "ℹ️ **אודות הבוט**\n\n"
                "🤖 **שם:** Video Info Bot\n"
                "📝 **תיאור:** בוט לניתוח ועיבוד קבצי וידאו\n"
                "🛠 **יכולות:**\n"
                "• ניתוח קבצי וידאו\n"
                "• המרת פורמטים\n"
                "• זיהוי איכות\n"
                "• שמירה לשימוש חוזר\n\n"
                "👨‍💻 **פיתוח:** Python + Pyrogram\n"
                "📅 **גרסה:** 2.0.0\n"
            )
            
        @self.app.on_message(filters.command(["adduser", "removeuser"]) & filters.user(1681880347))
        async def manage_users(client: Client, message: Message):
            """טיפול בפקודות ניהול משתמשים"""
            try:
                command = message.command[0]
                user_id = int(message.command[1])
            except (IndexError, ValueError):
                await message.reply_text("❌ שימוש שגוי. דוגמה: /adduser 123456789")
                return
                
            if command == "adduser":
                if self.user_service.add_user(user_id):
                    await message.reply_text(f"✅ משתמש {user_id} נוסף בהצלחה")
                else:
                    await message.reply_text(f"ℹ️ משתמש {user_id} כבר קיים במערכת")
            else:  # removeuser
                if self.user_service.remove_user(user_id):
                    await message.reply_text(f"✅ משתמש {user_id} הוסר בהצלחה")
                else:
                    await message.reply_text(f"❌ משתמש {user_id} לא נמצא במערכת")
                    
        @self.app.on_message(filters.command("users") & filters.user(1681880347))
        async def list_users(client: Client, message: Message):
            """הצגת רשימת משתמשים מורשים"""
            users = self.user_service.get_allowed_users()
            if users:
                users_text = "\n".join([f"• `{user}`" for user in users])
                await message.reply_text(
                    f"👥 **משתמשים מורשים:**\n\n{users_text}\n\n"
                    f"סה\"כ: {len(users)} משתמשים"
                )
            else:
                await message.reply_text("❌ אין משתמשים מורשים במערכת")
