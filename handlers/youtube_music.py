import logging
from pyrogram import filters
from pyrogram.types import Message
from core import app
from utils import check_blacklist, get_ydl, format_audio_keyboard
from database import add_session

logger = logging.getLogger(__name__)

YOUTUBE_MUSIC_DOMAINS = ("music.youtube.com",)

@app.on_message(filters.text & filters.private & (filters.regex(r"(?i).*\b(" + "|".join(YOUTUBE_MUSIC_DOMAINS) + r")\b.*")))
@check_blacklist
async def youtube_music_handler(_, message: Message, url_override: str = None, user_id_override: int = None):
    """Handles YouTube Music links."""
    url = url_override or message.text
    user_id = user_id_override or message.from_user.id
    username = message.from_user.username if not url_override else None

    if url_override:
        status_message = await message.edit_text("⏳ Получаю информацию о треке...")
    else:
        status_message = await message.reply_text("⏳ Получаю информацию о треке...", quote=True)

    try:
        ydl = get_ydl({'extract_flat': 'in_playlist'})
        info = await app.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
    except Exception as e:
        logger.error(f"Error fetching YouTube Music info for {url}: {e}")
        await status_message.edit_text("❌ Не удалось получить информацию. Убедитесь, что ссылка корректна и публично доступна.")
        return

    if not info:
        await status_message.edit_text("❌ Не удалось получить информацию. Попробуйте другую ссылку.")
        return

    if 'entries' in info and info['entries']:
        info = info['entries'][0]

    title = info.get('title', 'Без названия')
    author = info.get('artist') or info.get('uploader', 'Неизвестный исполнитель')
    
    keyboard = format_audio_keyboard()
    
    sent_message = await status_message.edit_text(
        f"🎵 **{title}**\n👤 __{author}__",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

    session_data = {
        'url': url,
        'user_id': user_id,
        'username': username,
        'chat_id': message.chat.id,
        'message_id': sent_message.id,
        'title': title,
        'author': author,
        'info': info,
        'type': 'youtube_music'
    }
    add_session(user_id, session_data)
