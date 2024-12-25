import os
import yaml
import logging
import asyncio
from config.settings import FILE_IDS_FILE

def load_file_ids() -> dict:
    """טעינת רשימת מזהי הקבצים מהקובץ"""
    if os.path.exists(FILE_IDS_FILE):
        with open(FILE_IDS_FILE, "r") as file:
            return yaml.safe_load(file) or {}
    return {}

def save_file_id(file_name: str, file_id: str) -> None:
    """שמירת מזהה קובץ חדש"""
    file_ids = load_file_ids()
    file_ids[file_name] = file_id
    with open(FILE_IDS_FILE, "w") as file:
        yaml.dump(file_ids, file)
    logging.info(f"נשמר file_id עבור {file_name}")

def check_existing_file(file_name: str) -> str:
    """בדיקה אם קובץ כבר קיים במערכת"""
    file_ids = load_file_ids()
    return file_ids.get(file_name)

async def convert_to_mp4(input_file: str, output_file: str) -> bool:
    """המרת קובץ וידאו לפורמט MP4"""
    try:
        process = await asyncio.create_subprocess_shell(
            f'ffmpeg -i "{input_file}" "{output_file}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logging.error(f"שגיאה בהמרת הקובץ ל-MP4: {e}")
        return False

async def create_thumbnail(input_file: str, thumbnail_file: str) -> bool:
    """יצירת תמונה ממוזערת לוידאו"""
    try:
        process = await asyncio.create_subprocess_shell(
            f'ffmpeg -i "{input_file}" -ss 00:00:01.000 -vframes 1 "{thumbnail_file}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logging.error(f"שגיאה ביצירת תמונה ממוזערת: {e}")
        return False
