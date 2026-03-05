import asyncio
import logging
from pyrogram import filters
from pyrogram.enums import ChatAction
from core import app
from database import update_session, update_user
from utils import format_video_keyboard, make_session_key, check_blacklist

logger = logging.getLogger(__name__)

@app.on_message(filters.regex(r"https?://(www\.)?youtu"))
@check_blacklist
async def handle_youtube_link(_, message):
    """Handles YouTube links."""
    update_user(message.from_user.id, {"id": message.from_user.id})
    url = message.text.strip()

    def fetch_info(url: str):
        from utils import get_ydl
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            }
        }
        with get_ydl(ydl_opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"yt-dlp failed to extract info for {url}", exc_info=True)
                return e

    await app.send_chat_action(message.chat.id, ChatAction.TYPING)
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, fetch_info, url)

    if isinstance(info, Exception) or not isinstance(info, dict):
        logger.error(f"Error fetching formats for {url}: {info}")
        error_message = "❌ **Ошибка при получении информации о видео.**\n"
        error_str = str(info)
        if "Sign in to confirm your age" in error_str:
            error_message += "Причина: Видео имеет возрастные ограничения."
        elif "This video is not available" in error_str:
            error_message += "Причина: Видео недоступно в вашем регионе."
        elif "copyright" in error_str:
            error_message += "Причина: Видео защищено авторским правом."
        else:
            error_message += "Причина: Неизвестная ошибка. Попробуйте позже."
        return await message.reply_text(error_message)

    title = ''.join(c for c in info.get('title', '') if c.isalnum() or c in (' ', '.', '_', '-')).strip()
    author = info.get('uploader', 'Unknown')

    keyboard = format_video_keyboard(info)
    reply = await message.reply_photo(
        info.get('thumbnail'),
        caption=f"**{title}**\n__{author}__",
        reply_markup=keyboard
    )

    session_key = make_session_key(reply)
    session_data = {
        'url': url,
        'info': info,
        'title': title,
        'author': author,
        'type': 'video',
        'initiator': message.from_user.id
    }
    update_session(session_key, session_data)
