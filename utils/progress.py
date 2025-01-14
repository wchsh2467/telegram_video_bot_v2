import time
import math
from typing import Callable, Union
from pyrogram.types import Message
from .rate_limiter import TelegramRateLimiter
import logging

class ProgressBar:
    def __init__(self, total: int, message: Message, action: str):
        self.total = total
        self.message = message
        self.action = action
        self.start_time = time.time()
        self.last_edit_time = 0
        self.last_percentage = 0
        self.rate_limiter = TelegramRateLimiter()  # יצירת מופע של rate limiter
        
    async def update(self, current: int):
        now = time.time()
        percentage = current * 100 / self.total
        
        # עדכון רק כל 2% או כל 3 שניות
        if (percentage - self.last_percentage < 2) and (now - self.last_edit_time < 3):
            return
            
        try:
            # בדיקת rate limit לפני העדכון
            await self.rate_limiter.acquire(
                self.message.chat.id, 
                is_group=self.message.chat.type != "private"
            )
            
            # יצירת פס התקדמות ויזואלי
            progress_length = 20
            filled_length = int(progress_length * current // self.total)
            progress_bar = '█' * filled_length + '░' * (progress_length - filled_length)
            
            # המרת גדלים למונחים אנושיים
            def humanbytes(size: int) -> str:
                if size is None or size == 0:
                    return "0B"
                units = ['B', 'KB', 'MB', 'GB', 'TB']
                i = int(math.floor(math.log(size, 1024)))
                s = round(size / math.pow(1024, i), 2)
                return f"{s}{units[i]}"
                
            def humantime(seconds: int) -> str:
                if seconds == 0:
                    return "0s"
                minutes, seconds = divmod(int(seconds), 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    return f"{hours}h{minutes}m"
                elif minutes > 0:
                    return f"{minutes}m{seconds}s"
                else:
                    return f"{seconds}s"
            
            # חישוב מהירות וזמן שנותר
            elapsed_time = now - self.start_time
            speed = current / elapsed_time if elapsed_time > 0 else 0
            eta = (self.total - current) / speed if speed > 0 else 0
            
            # יצירת הודעת התקדמות
            text = f"**{self.action}**\n\n"
            text += f"**{progress_bar}** `{percentage:.1f}%`\n\n"
            text += f"**⚡️ מהירות:** `{humanbytes(speed)}/s`\n"
            text += f"**📊 הושלם:** `{humanbytes(current)} / {humanbytes(self.total)}`\n"
            text += f"**⏱ זמן נותר:** `{humantime(eta)}`"
            
            await self.message.edit_text(text)
            
            # עדכון המצב האחרון
            self.last_percentage = percentage
            self.last_edit_time = now
            
        except Exception as e:
            logging.error(f"Error updating progress: {e}")

def get_progress_callback(message: Message, action: str) -> Callable:
    """יוצר פונקציית התקדמות עבור פעולות טלגרם"""
    progress_bar = None
    
    async def progress(current: int, total: int):
        nonlocal progress_bar
        if progress_bar is None:
            progress_bar = ProgressBar(total, message, action)
        await progress_bar.update(current)
        
    return progress
