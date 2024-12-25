import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_PATH, TARGET_GROUP_ID, ADMIN_USER_ID
from services.video_service import VideoService
from services.user_service import UserService

# הגדרת הלוגר
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# יצירת אובייקט הבוט
app = Client("video_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# יצירת שירותים
video_service = VideoService(app, DOWNLOAD_PATH)
user_service = UserService()

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    """טיפול בהודעות וידאו"""
    # בדיקת הרשאות המשתמש
    user_id_str = str(message.from_user.id)
    if not user_service.is_user_allowed(user_id_str):
        await message.reply_text("אין לך הרשאה להשתמש בבוט זה. 🚫")
        return

    # בדיקה אם זו הודעת וידאו או מסמך
    if message.document:
        # בדיקת סיומת הקובץ
        if not message.document.file_name.lower().endswith(('.mkv', '.avi', '.mov', '.mp4', '.m4v', '.flv', '.webm', '.ts', '.mts', '.wmv', '.vob', '.dat', '.rm', '.rmvb', '.divx', '.Mpg', '.mpg')):
            await message.reply_text("הקובץ אינו בפורמט וידאו נתמך. 🚫")
            return

    # עיבוד הוידאו
    await video_service.process_video_message(message)

@app.on_message(filters.private & filters.command("update"))
async def update_users(client, message):
    """עדכון רשימת המשתמשים המורשים"""
    user_id_str = str(message.from_user.id)
    if user_id_str != ADMIN_USER_ID:
        await message.reply_text("אין לך הרשאה לעדכן את רשימת המשתמשים. 🚫")
        return

    try:
        # קבלת רשימת המשתמשים החדשה
        new_users = message.text.split()[1:]
        if not new_users:
            await message.reply_text("אנא ציין רשימת מזהי משתמשים לעדכון.")
            return

        # עדכון רשימת המשתמשים
        added_count, invalid_ids = user_service.add_users(','.join(new_users))
        
        # יצירת הודעת תשובה
        response = f"נוספו {added_count} משתמשים בהצלחה."
        if invalid_ids:
            response += f"\nמזהים לא תקינים: {', '.join(invalid_ids)}"
        
        await message.reply_text(response)

    except Exception as e:
        logging.error(f"שגיאה בעדכון רשימת המשתמשים: {e}")
        await message.reply_text("אירעה שגיאה בעדכון רשימת המשתמשים.")

@app.on_callback_query(filters.regex("^cancel_download_"))
async def handle_cancel_download(client, callback_query):
    """טיפול בלחיצה על כפתור ביטול הורדה"""
    try:
        # חילוץ מזהה המשתמש מה-callback_data
        user_id = int(callback_query.data.split('_')[-1])
        
        # וידוא שהמשתמש מבטל את ההורדה שלו
        if callback_query.from_user.id != user_id:
            await callback_query.answer("אינך יכול לבטל הורדות של משתמשים אחרים", show_alert=True)
            return
        
        await video_service.cancel_download(user_id)
        await callback_query.answer("ההורדה מבוטלת...", show_alert=True)
    
    except Exception as e:
        logging.error(f"שגיאה בביטול ההורדה: {e}")
        await callback_query.answer("אירעה שגיאה בביטול ההורדה", show_alert=True)

if __name__ == "__main__":
    logging.info("מתחיל את הבוט")
    app.run()
