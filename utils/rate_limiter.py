import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Deque
import logging

logger = logging.getLogger(__name__)

class TelegramRateLimiter:
    """
    מנהל הגבלות קצב שליחת הודעות בטלגרם
    - בצ'אט פרטי: הודעה אחת בשנייה
    - בקבוצה: 20 הודעות בדקה
    """
    
    def __init__(self):
        # שמירת היסטוריית הודעות לכל צ'אט
        self.private_chat_history: Dict[int, Deque[float]] = defaultdict(deque)
        self.group_chat_history: Dict[int, Deque[float]] = defaultdict(deque)
        
        # מגבלות
        self.PRIVATE_MESSAGE_INTERVAL = 1.0  # שנייה בין הודעות בצ'אט פרטי
        self.GROUP_MESSAGE_LIMIT = 20        # הודעות בדקה בקבוצה
        self.GROUP_WINDOW_SIZE = 60.0        # חלון זמן בשניות לקבוצה
        
        logger.info("TelegramRateLimiter initialized")

    async def acquire(self, chat_id: int, is_group: bool = False) -> None:
        """
        בדיקה והמתנה לפי מגבלות הצ'אט
        
        Args:
            chat_id (int): מזהה הצ'אט
            is_group (bool): האם זו קבוצה
        """
        current_time = time.time()
        
        if is_group:
            await self._handle_group_message(chat_id, current_time)
        else:
            await self._handle_private_message(chat_id, current_time)

    async def _handle_group_message(self, chat_id: int, current_time: float) -> None:
        """טיפול בהודעות קבוצה"""
        history = self.group_chat_history[chat_id]
        
        # ניקוי היסטוריה ישנה
        while history and current_time - history[0] >= self.GROUP_WINDOW_SIZE:
            history.popleft()
        
        # בדיקה אם הגענו למגבלה
        if len(history) >= self.GROUP_MESSAGE_LIMIT:
            wait_time = history[0] + self.GROUP_WINDOW_SIZE - current_time
            if wait_time > 0:
                logger.debug(f"Waiting {wait_time:.2f}s for group {chat_id} rate limit")
                await asyncio.sleep(wait_time)
                current_time = time.time()
        
        # הוספת הזמן הנוכחי להיסטוריה
        history.append(current_time)
        logger.debug(f"Group {chat_id} message count in window: {len(history)}")

    async def _handle_private_message(self, chat_id: int, current_time: float) -> None:
        """טיפול בהודעות פרטיות"""
        history = self.private_chat_history[chat_id]
        
        if history:
            time_since_last = current_time - history[-1]
            if time_since_last < self.PRIVATE_MESSAGE_INTERVAL:
                wait_time = self.PRIVATE_MESSAGE_INTERVAL - time_since_last
                logger.debug(f"Waiting {wait_time:.2f}s for private chat {chat_id} rate limit")
                await asyncio.sleep(wait_time)
                current_time = time.time()
        
        # עדכון זמן ההודעה האחרונה
        history.append(current_time)
        
        # שמירה רק על ההודעה האחרונה
        if len(history) > 1:
            history.popleft()

    def cleanup(self) -> None:
        """ניקוי היסטוריית הודעות ישנה"""
        current_time = time.time()
        
        # ניקוי היסטוריית קבוצות
        for chat_id in list(self.group_chat_history.keys()):
            history = self.group_chat_history[chat_id]
            while history and current_time - history[0] >= self.GROUP_WINDOW_SIZE:
                history.popleft()
            if not history:
                del self.group_chat_history[chat_id]
        
        # ניקוי היסטוריית צ'אטים פרטיים ישנים (מעל שעה)
        for chat_id in list(self.private_chat_history.keys()):
            history = self.private_chat_history[chat_id]
            if history and current_time - history[-1] >= 3600:  # שעה
                del self.private_chat_history[chat_id]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
