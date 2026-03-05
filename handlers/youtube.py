import asyncio
import logging
from pyrogram import filters
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

    def fetch_formats(url: str):
        from utils import get_ydl
        ydl_opts = {
            'quiet': False,
            'skip_download': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            }
        }
        with get_ydl(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    loop = asyncio.get_running_loop()
    try:
        await app.send_chat_action(message.chat.id, "typing")
        info = await loop.run_in_executor(None, fetch_formats, url)
    except Exception as e:
        logger.error(f"Error fetching formats for {url}: {e}")
        error_message = "❌ **Ошибка при получении информации о видео.**\n"
        if "Sign in to confirm your age" in str(e):
            error_message += "Причина: Видео имеет возрастные ограничения."
        elif "This video is not available" in str(e):
            error_message += "Причина: Видео недоступно в вашем регионе."
        elif "copyright" in str(e):
            error_message += "Причина: Видео защищено авторским правом."
        else:
            error_message += "Причина: Неизвестная ошибка. Попробуйте позже."
        return await message.reply_text(error_message)

    title = ''.join(c for c in info.get('title', '') if c.isalnum() or c in (' ', '.', '_', '-')).strip()
    author = info.get('uploader', 'Unknown')

    keyboard = format_video_keyboard(info)
    reply = await message.reply_photo(
        info.get('thumbnail'),
        caption=f"**{title}**\n_{author}_",
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
