import asyncio
import time
import logging
import requests
import yt_dlp
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from functools import wraps
from database import is_blacklisted
from core import safe_edit_text

logger = logging.getLogger(__name__)
ACTIVITY_LOG_FILE = "activity.log"

AUDIO_FORMATS = {
    "mp3": "👎 MP3 👎",
    "opus": "✨ Opus ✨",
    "flac": "👾 FLAC 👾",
    "wav": "🤓 WAV 🤓"
}

def log_activity(user_id, username, url, format_choice, file_size_mb):
    """Logs user download activity."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_message = (
        f"[{timestamp}] User: {user_id} (@{username if username else 'N/A'}), "
        f"URL: {url}, Format: {format_choice}, Size: {file_size_mb:.2f} MB\n"
    )
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_message)

def _progress_hook(d, loop, status_message, last_status):
    """Shared download progress hook."""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        if not total:
            return
        downloaded = d.get('downloaded_bytes', 0)
        percent = int(downloaded * 100 / total)
        status_text = f"📥 Скачивание... {percent}%"
        
        if status_text != last_status.get("text"):
            last_status["text"] = status_text
            asyncio.run_coroutine_threadsafe(
                safe_edit_text(status_message, status_text),
                loop
            )

def _send_progress(current, total, status_message, last_status, loop):
    """Shared upload progress callback for Pyrogram."""
    percent = int(current * 100 / total)
    status_text = f"🚀 Отправка... {percent}%"
    if status_text != last_status.get("text"):
        last_status["text"] = status_text
        asyncio.run_coroutine_threadsafe(
            safe_edit_text(status_message, status_text),
            loop
        )

async def download_thumbnail(info: dict, base_path: str) -> str | None:
    """Downloads a thumbnail and returns its path."""
    if not info: return None
    thumb_url = info.get('thumbnail') or (info.get('thumbnails', [{}])[-1].get('url'))
    if not thumb_url:
        return None
    
    thumb_path = base_path + '.jpg'
    try:
        r = requests.get(thumb_url, timeout=10)
        r.raise_for_status()
        with open(thumb_path, 'wb') as f:
            f.write(r.content)
        return thumb_path
    except requests.RequestException as e:
        logger.warning(f"Failed to download thumbnail: {e}")
        return None

def check_blacklist(func):
    """Decorator to check if a user is blacklisted."""
    @wraps(func)
    async def wrapper(client, message):
        user_id = message.from_user.id
        if is_blacklisted(user_id):
            await message.reply_text("Вы были заблокированы.")
            return
        return await func(client, message)
    return wrapper

def get_ydl(opts):
    """Initializes and returns a yt_dlp.YoutubeDL instance with given options."""
    default = {}
    default.update(opts)
    return yt_dlp.YoutubeDL(default)

def format_video_keyboard(info):
    """Formats the keyboard with available video resolutions."""
    formats = info.get('formats', [])
    
    # Get unique video heights
    unique_heights = sorted(list(set(
        f['height'] for f in formats 
        if isinstance(f, dict) and f.get('height') and f.get('vcodec') != 'none'
    )), reverse=True)

    kb = []
    row = []
    for height in unique_heights:
        emoji = '🖥' if height >= 720 else '📺'
        label = f"{height}p {emoji}"
        row.append(InlineKeyboardButton(label, callback_data=f"video:{height}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    
    if row:
        kb.append(row)
        
    kb.append([InlineKeyboardButton("🎧 Только звук", callback_data="audio")])
    return InlineKeyboardMarkup(kb)

def format_audio_keyboard():
    """Formats the keyboard with available audio formats."""
    kb = []
    row = []
    for key, label in AUDIO_FORMATS.items():
        row.append(InlineKeyboardButton(label, callback_data=f"audioformat:{key}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb)

def get_message_id(message):
    """Gets the message ID from a Pyrogram message object for session keying."""
    mid = getattr(message, "message_id", None)
    if mid is None:
        mid = getattr(message, "id", None)
    return mid

def make_session_key(message):
    """Creates a unique session key from a message."""
    mid = get_message_id(message)
    if mid is None:
        raise ValueError("Cannot determine message id for session key")
    return f"{message.chat.id}:{mid}"
