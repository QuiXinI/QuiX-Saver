import logging
from pyrogram import filters
from pyrogram.types import Message
from core import app
from utils import check_blacklist, get_ydl, format_video_keyboard
from database import add_session

logger = logging.getLogger(__name__)

# Custom filter to capture YouTube links but exclude YouTube Music
def youtube_link_filter(_, __, m: Message):
    if not m.text:
        return False
    text = m.text.lower()
    # Explicitly exclude YouTube Music links
    if "music.youtube.com" in text:
        return False
    # Capture general YouTube links
    if "youtube.com" in text or "youtu.be" in text:
        return True
    return False

youtube_filter = filters.create(youtube_link_filter)

@app.on_message(filters.text & filters.private & youtube_filter)
@check_blacklist
async def youtube_handler(_, message: Message, url_override: str = None, user_id_override: int = None):
    """Handles YouTube links, excluding YouTube Music."""
    url = url_override or message.text
    user_id = user_id_override or message.from_user.id
    username = message.from_user.username if not url_override else None

    if url_override:
        # When called from 'again', message is the bot's status message. Edit it.
        status_message = await message.edit_text("⏳ Получаю информацию о видео...")
    else:
        # For a new link, reply to the user's message.
        status_message = await message.reply_text("⏳ Получаю информацию о видео...", quote=True)

    try:
        ydl = get_ydl({'extract_flat': 'in_playlist'})
        info = await app.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
    except Exception as e:
        logger.error(f"Error fetching YouTube info for {url}: {e}")
        await status_message.edit_text("❌ Не удалось получить информацию. Убедитесь, что ссылка корректна и публично доступна.")
        return

    if not info:
        await status_message.edit_text("❌ Не удалось получить информацию. Попробуйте другую ссылку.")
        return

    # For playlists, take the first video
    if 'entries' in info and info['entries']:
        info = info['entries'][0]

    # Prepare data for the message and session
    title = info.get('title', 'Без названия')
    author = info.get('uploader', 'Неизвестный автор')
    
    keyboard = format_video_keyboard(info)
    
    sent_message = await status_message.edit_text(
        f"▶️ **{title}**\n👤 __{author}__",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

    # Create and save the session, anchored to the bot's reply message
    session_data = {
        'url': url,
        'user_id': user_id,
        'username': username,
        'chat_id': message.chat.id,
        'message_id': sent_message.id,
        'title': title,
        'author': author,
        'info': info, # Cache the formats info
        'type': 'youtube'
    }
    add_session(user_id, session_data)
