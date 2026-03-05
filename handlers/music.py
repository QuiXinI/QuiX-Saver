import asyncio
import logging
from pyrogram import filters
from pyrogram.enums import ChatAction
from core import app
from database import update_session, update_user
from utils import format_audio_keyboard, make_session_key, check_blacklist

logger = logging.getLogger(__name__)

@app.on_message(filters.regex(r"https?://(music\.youtube\.com|music\.yandex\.ru)"))
@check_blacklist
async def handle_music_link(_, message):
    """Handles music links from YouTube Music and Yandex.Music."""
    update_user(message.from_user.id, {"id": message.from_user.id})
    url = message.text.strip()

    def fetch_info(url: str):
        from utils import get_ydl
        ydl_opts = {'quiet': True, 'skip_download': True, 'no_warnings': True}
        if "yandex" in url:
            # yt-dlp requires cookies to get info from Yandex.Music
            ydl_opts['cookiesfrombrowser'] = ('firefox',)
        with get_ydl(ydl_opts) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as e:
                # Log the full error for debugging
                logger.error(f"yt-dlp failed to extract info for {url}", exc_info=True)
                # Return the exception to be handled in the main thread
                return e

    await app.send_chat_action(message.chat.id, ChatAction.TYPING)
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, fetch_info, url)

    # Handle cases where yt-dlp failed
    if isinstance(info, Exception) or not isinstance(info, dict):
        error_message = (
            "❌ **Не удалось получить информацию о треке.**\n\n"
            "Возможные причины:\n"
            "1. Трек недоступен в вашем регионе.\n"
            "2. Что-то отвалилось на сервере. В ближайшее время починим."
        )
        if isinstance(info, Exception):
             # Log the specific error yt-dlp returned
            logger.error(f"Error fetching music info for {url}: {info}")
        return await message.reply_text(error_message)


    full_title = info.get('title', '')
    author = info.get('artist') or info.get('uploader', 'Unknown')
    title = full_title.replace(author, '').strip().replace('  ', ' ').strip('- ') if author and author in full_title else full_title

    keyboard = format_audio_keyboard()
    reply = await message.reply_text(
        f"**{title}**\n__{author}__",
        reply_markup=keyboard
    )

    session_key = make_session_key(reply)
    session_data = {
        'url': url,
        'info': info,
        'title': title,
        'author': author,
        'type': 'audio',
        'initiator': message.from_user.id
    }
    update_session(session_key, session_data)
