import os
import logging
import asyncio
from collections import defaultdict
from moviepy.editor import VideoFileClip
from config.settings import TARGET_GROUP_ID
from utils.helpers import clean_filename, get_video_caption, wait_for_file_release, wait_and_delete
from services.file_service import check_existing_file, save_file_id, convert_to_mp4, create_thumbnail
from services.queue_service import QueueService
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class VideoService:
    def __init__(self, app, download_path):
        self.app = app
        self.download_path = download_path
        self.queue_service = QueueService()  # הוספת שירות התור
        self.active_downloads = defaultdict(asyncio.Event)  # אירועי ביטול לפי ID משתמש

    async def cancel_download(self, user_id: int) -> None:
        """ביטול הורדה של משתמש"""
        # ביטול ההורדה הפעילה
        if user_id in self.active_downloads:
            self.active_downloads[user_id].set()
            logging.info(f"הורדה בוטלה עבור משתמש {user_id}")
        
        # ביטול כל ההורדות של המשתמש בתור
        await self.queue_service.cancel_user_downloads(user_id)
        
        # אם יש קבצים בתור, מתחיל לעבד את הבא בתור
        if len(self.queue_service.upload_queue) > 0:
            next_message = self.queue_service.upload_queue[0]
            asyncio.create_task(self.process_video_message(next_message))

    def _check_cancellation(self, user_id: int) -> None:
        """בדיקה אם ההורדה בוטלה"""
        if user_id in self.active_downloads and self.active_downloads[user_id].is_set():
            raise asyncio.CancelledError("ההורדה בוטלה על ידי המשתמש")

    async def process_video_message(self, message):
        """עיבוד הודעת וידאו חדשה"""
        file = message.video or message.document
        original_file_name = file.file_name if file.file_name else "video.mp4"
        clean_file_name = clean_filename(original_file_name)
        user_id = message.from_user.id

        # בדיקת קובץ קיים
        existing_file_id = check_existing_file(clean_file_name)
        if existing_file_id:
            await self._send_existing_video(message, existing_file_id, clean_file_name)
            return

        # בדיקת מיקום בתור לפני הוספה
        is_first = len(self.queue_service.user_queue) == 0 or self.queue_service.is_first_user(user_id)
        
        # הוספה לתור
        if not is_first:
            # משתמש לא ראשון - מוסיף עם הודעת המתנה
            position = await self.queue_service.add_to_queue(message)
            queue_message = await message.reply(f"הקובץ התקבל ✅\nמיקומך בתור: {position}")
            self.queue_service.queue_messages[message.id] = queue_message
        else:
            # משתמש ראשון - מוסיף בלי הודעת המתנה
            await self.queue_service.add_to_queue(message)
        
        # אם זה לא הקובץ הראשון בתור, מחכים
        if not self.queue_service.is_first_in_queue(message.id):
            logging.info(f"Message {message.id} waiting in queue")
            return
        
        try:
            # הודעת תחילת הורדה
            download_message = await message.reply("הקובץ התקבל\nאנא המתן...✅")
            await asyncio.sleep(3)
            await download_message.delete()

            # הורדת הקובץ
            file_path = await self._download_video(message, file, clean_file_name)
            if file_path:
                # עיבוד הוידאו
                processed_video = await self._process_video(message, file_path, clean_file_name)
                if processed_video:
                    # שליחת הוידאו
                    await self._send_processed_video(message, processed_video)
                    
                    # הסרה מהתור רק אחרי שהקובץ נשלח בהצלחה
                    await self.queue_service.remove_from_queue(message.id, user_id)
                    
                    # מעבר לקובץ הבא בתור
                    if len(self.queue_service.upload_queue) > 0:
                        next_message = self.queue_service.upload_queue[0]
                        asyncio.create_task(self.process_video_message(next_message))

        except Exception as e:
            logging.error(f"שגיאה בעיבוד הוידאו: {e}")
            await message.reply_text("אירעה שגיאה בעיבוד הוידאו. אנא נסה שוב.")
            # במקרה של שגיאה, מסיר מהתור ועובר לבא
            await self.queue_service.remove_from_queue(message.id, user_id)
            if len(self.queue_service.upload_queue) > 0:
                next_message = self.queue_service.upload_queue[0]
                asyncio.create_task(self.process_video_message(next_message))

    async def _send_existing_video(self, message, file_id, file_name):
        """שליחת וידאו קיים"""
        caption_without_extension = os.path.splitext(file_name)[0]
        await message.reply_video(
            video=file_id,
            caption=caption_without_extension
        )
        logging.info(f"הקובץ {file_name} כבר קיים ונשלח ישירות מהקבוצה.")

    async def _download_video(self, message, file, clean_file_name):
        """הורדת קובץ הוידאו"""
        try:
            file_path = os.path.join(self.download_path, clean_file_name)
            await self._download_with_progress(message, file_path)
            logging.info(f"הקובץ הורד בהצלחה ל- {file_path}")
            return file_path
        except (TimeoutError, ConnectionError) as e:
            logging.error(f"שגיאת רשת בהורדת הקובץ: {e}")
            await message.reply_text("אירעה שגיאת רשת בהורדת הקובץ. אנא נסה שוב.")
            # הסרה מהתור במקרה של שגיאת רשת
            await self.queue_service.remove_from_queue(message.id, message.from_user.id)
            return None
        except Exception as e:
            logging.error(f"נכשל בהורדת הקובץ: {e}")
            await message.reply_text("אירעה שגיאה בהורדת הקובץ. אנא נסה שוב.")
            # הסרה מהתור במקרה של שגיאה כללית
            await self.queue_service.remove_from_queue(message.id, message.from_user.id)
            return None

    async def _process_video(self, message, file_path, clean_file_name):
        """עיבוד קובץ הוידאו"""
        processing_message = None
        try:
            # הודעת התחלת עיבוד
            processing_message = await message.reply("🔄 מעבד את הוידאו...")
            
            base_name, ext = os.path.splitext(clean_file_name)
            original_path = file_path  # שמירת הנתיב המקורי
            
            # המרה ל-MP4 אם נדרש
            if ext.lower() != '.mp4':
                await processing_message.edit_text("🔄 ממיר את הוידאו ל-MP4...")
                mp4_file = os.path.join(self.download_path, f"{base_name}.mp4")
                if not await convert_to_mp4(file_path, mp4_file):
                    await processing_message.edit_text("❌ שגיאה בהמרת הוידאו")
                    await self.queue_service.remove_from_queue(message.id, message.from_user.id)
                    return None
                file_path = mp4_file

            # יצירת תמונה ממוזערת
            await processing_message.edit_text("🔄 יוצר תמונה ממוזערת...")
            thumbnail_file = os.path.join(self.download_path, f"{base_name}.jpg")
            try:
                thumbnail_success = await create_thumbnail(file_path, thumbnail_file)
                if not thumbnail_success:
                    logging.warning("נכשל ביצירת תמונה ממוזערת, ממשיך בלעדיה")
                    thumbnail_file = None
            except Exception as e:
                logging.warning(f"שגיאה ביצירת תמונה ממוזערת: {e}")
                thumbnail_file = None
            
            # חישוב משך הוידאו
            await processing_message.edit_text("🔄 מחשב את משך הוידאו...")
            video = VideoFileClip(file_path)
            duration = int(video.duration)
            video.close()
            
            await processing_message.edit_text("✅ העיבוד הושלם!")
            await asyncio.sleep(3)
            await processing_message.delete()

            return {
                'file_path': file_path,
                'thumbnail_path': thumbnail_file,  # יכול להיות None
                'duration': duration,
                'original_path': original_path if original_path != file_path else None
            }
            
        except Exception as e:
            if processing_message:
                await processing_message.edit_text("❌ שגיאה בעיבוד הוידאו")
                await asyncio.sleep(3)
                await processing_message.delete()
            logging.error(f"שגיאה בעיבוד הוידאו: {e}")
            await self.queue_service.remove_from_queue(message.id, message.from_user.id)
            return None

    async def _send_processed_video(self, message, video_data):
        """שליחת הוידאו המעובד"""
        try:
            logging.info("מתחיל שליחת וידאו...")
            caption = get_video_caption(video_data['file_path'])
            logging.info(f"נוצרה כותרת: {caption}")
            
            # שליחה למשתמש
            logging.info("שולח למשתמש...")
            await self._upload_with_progress(message, video_data, caption)
            logging.info("נשלח למשתמש בהצלחה")
            
            # שליחה לקבוצת היעד
            logging.info("מכין פרמטרים לשליחה לקבוצת היעד...")
            send_params = {
                'chat_id': TARGET_GROUP_ID,
                'video': video_data['file_path'],
                'duration': video_data['duration'],
                'caption': caption,
                'supports_streaming': True
            }
            
            # הוספת תמונה ממוזערת רק אם היא קיימת
            if video_data.get('thumbnail_path'):
                logging.info(f"מוסיף תמונה ממוזערת: {video_data['thumbnail_path']}")
                if os.path.exists(video_data['thumbnail_path']):
                    send_params['thumb'] = video_data['thumbnail_path']
                else:
                    logging.warning("קובץ התמונה הממוזערת לא נמצא")
            
            logging.info(f"שולח לקבוצת היעד {TARGET_GROUP_ID}...")
            sent_message = await self.app.send_video(**send_params)
            logging.info("הוידאו נשלח בהצלחה לקבוצת היעד")
            
            # שמירת מזהה הקובץ
            file_name = os.path.basename(video_data['file_path'])
            logging.info(f"שומר file_id עבור {file_name}")
            save_file_id(file_name, sent_message.video.file_id)
            
            # ניקוי קבצים
            logging.info("מנקה קבצים זמניים...")
            await self._cleanup_files(video_data)
            logging.info("תהליך השליחה הושלם בהצלחה")
            
        except Exception as e:
            logging.error(f"שגיאה בשליחת הוידאו: {str(e)}", exc_info=True)
            await message.reply_text("אירעה שגיאה בשליחת הוידאו. אנא נסה שוב.")
            await self.queue_service.remove_from_queue(message.id, message.from_user.id)

    async def _download_with_progress(self, message, file_path):
        """הורדת קובץ עם פס התקדמות"""
        user_id = message.from_user.id
        self.active_downloads[user_id] = asyncio.Event()  # איפוס אירוע הביטול
        
        # יצירת כפתור ביטול
        cancel_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("ביטול ❌", callback_data=f"cancel_download_{user_id}")]
        ])
        
        progress_message = await message.reply("📥 הורדה החלה...", reply_markup=cancel_button)
        last_percentage = 0
        last_update_time = asyncio.get_event_loop().time()
        downloaded_size = 0

        async def progress(current, total):
            try:
                self._check_cancellation(user_id)
                
                nonlocal last_percentage, last_update_time, downloaded_size
                percentage = int(current * 100 / total)
                current_time = asyncio.get_event_loop().time()
                time_diff = current_time - last_update_time
                
                if percentage >= last_percentage + 5 or time_diff >= 3:
                    speed = (current - downloaded_size) / (1024 * 1024 * time_diff) if time_diff > 0 else 0
                    downloaded_size = current
                    last_update_time = current_time
                    last_percentage = percentage
                    
                    filled = int(percentage / 10)
                    empty = 10 - filled
                    progress_bar = "▰" * filled + "▱" * empty
                    
                    new_text = (
                        f"📥 מוריד את הקובץ...\n"
                        f"{progress_bar} {percentage}%\n"
                        f"⚡ מהירות: {speed:.1f} MB/s\n"
                        f"📊 גודל: {total / (1024 * 1024):.1f} MB"
                    )
                    
                    # בדיקה אם הטקסט השתנה לפני העדכון
                    if progress_message.text != new_text:
                        try:
                            await progress_message.edit_text(
                                new_text,
                                reply_markup=cancel_button
                            )
                        except Exception as e:
                            if "MESSAGE_NOT_MODIFIED" not in str(e):
                                logging.warning(f"שגיאה בעדכון סטטוס ההורדה: {e}")
            except asyncio.CancelledError:
                raise

        try:
            await message.download(file_name=file_path, progress=progress)
            await progress_message.edit_text("✅ ההורדה הושלמה בהצלחה!")
            await asyncio.sleep(3)
            await progress_message.delete()
        except asyncio.CancelledError:
            await progress_message.edit_text("❌ ההורדה בוטלה")
            await asyncio.sleep(3)
            await progress_message.delete()
            raise
        except Exception as e:
            await progress_message.edit_text("❌ שגיאה בהורדת הקובץ")
            raise e
        finally:
            if user_id in self.active_downloads:
                del self.active_downloads[user_id]

    async def _upload_with_progress(self, message, video_data, caption):
        """העלאת קובץ עם פס התקדמות"""
        progress_message = await message.reply("📤 מתחיל העלאה...")
        last_percentage = 0
        last_update_time = asyncio.get_event_loop().time()
        uploaded_size = 0

        async def progress(current, total):
            try:
                nonlocal last_percentage, last_update_time, uploaded_size
                percentage = int(current * 100 / total)
                current_time = asyncio.get_event_loop().time()
                time_diff = current_time - last_update_time
                
                # עדכון כל 5 אחוזים או כל 3 שניות, מה שקורה קודם
                if percentage >= last_percentage + 5 or time_diff >= 3:
                    # חישוב מהירות ההעלאה
                    speed = (current - uploaded_size) / (1024 * 1024 * time_diff) if time_diff > 0 else 0
                    uploaded_size = current
                    last_update_time = current_time
                    last_percentage = percentage
                    
                    # יצירת פס התקדמות
                    filled = int(percentage / 10)
                    empty = 10 - filled
                    progress_bar = "▰" * filled + "▱" * empty
                    
                    try:
                        await progress_message.edit_text(
                            f"📤 מעלה את הקובץ...\n"
                            f"{progress_bar} {percentage}%\n"
                            f"⚡ מהירות: {speed:.1f} MB/s\n"
                            f"📊 גודל: {total / (1024 * 1024):.1f} MB"
                        )
                    except Exception as e:
                        logging.warning(f"שגיאה בעדכון סטטוס ההעלאה: {e}")

            except Exception as e:
                logging.error(f"שגיאה בעדכון סטטוס ההעלאה: {e}")

        try:
            await message.reply_video(
                video=video_data['file_path'],
                thumb=video_data['thumbnail_path'],
                duration=video_data['duration'],
                caption=caption,
                supports_streaming=True,
                progress=progress
            )
            await progress_message.edit_text("✅ ההעלאה הושלמה בהצלחה!")
            await asyncio.sleep(3)
            await progress_message.delete()
        except Exception as e:
            await progress_message.edit_text("❌ שגיאה בהעלאת הקובץ")
            raise e

    async def _cleanup_files(self, video_data):
        """ניקוי קבצים זמניים"""
        # המתנה לשחרור הקבצים
        await wait_for_file_release(video_data['file_path'])
        
        # מחיקת הקבצים
        if video_data.get('original_path'):  # מחיקת קובץ המקור אם קיים
            await wait_and_delete(video_data['original_path'])
        await wait_and_delete(video_data['file_path'])
        await wait_and_delete(video_data['thumbnail_path'])
        logging.info("קבצים זמניים נמחקו בהצלחה.")
