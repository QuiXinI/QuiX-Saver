import asyncio
import logging
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core import app, safe_edit_text
from database import get_session, update_session, get_user, update_user
from utils import make_session_key, format_video_keyboard, format_audio_keyboard, check_blacklist
from .download_logic import handle_video_download, handle_music_download, handle_video_to_audio_download

logger = logging.getLogger(__name__)

# --- Helper Functions for Callbacks ---

def _get_session_data(cq: CallbackQuery):
    """Retrieves session data for a callback query."""
    session_key = make_session_key(cq.message)
    session = get_session(session_key)
    if not session:
        # Fallback for old sessions keyed by user_id
        session = get_session(str(cq.from_user.id))
        if session:
            # Migrate old session to new key
            update_session(session_key, session)
    return session

# --- Main Callback Handler ---

@app.on_callback_query()
@check_blacklist
async def callback_handler(__, cq: CallbackQuery):
    """Handles all callback queries."""
    user_id = cq.from_user.id
    if not get_user(user_id):
        update_user(user_id, {"id": user_id})

    session = _get_session_data(cq)
    if not session:
        return await cq.answer("⚠️ Сессия истекла или не найдена. Пожалуйста, отправьте ссылку заново.", show_alert=True)

    if session.get('initiator') != user_id:
        return await cq.answer("🔒 Это не ваш запрос.", show_alert=True)

    await cq.message.edit_reply_markup(None)
    data = cq.data
    
    if data == "again":
        return await handle_again(cq, session)

    status_message = await cq.message.reply_text("⏳ Подготовка к скачиванию...")
    
    loop = asyncio.get_running_loop()
    last_status = {"text": None}

    try:
        if data.startswith('video:'):
            await handle_video_download(cq, session, data, status_message, loop, last_status)
        elif data.startswith('audioformat:'):
            await handle_music_download(cq, session, data, status_message, loop, last_status)
        elif data == 'audio':
            await handle_video_to_audio_download(cq, session, status_message, loop, last_status)
    except Exception as e:
        logger.error(f"Download failed for user {user_id}: {e}", exc_info=True)
        await safe_edit_text(status_message, f"❌ **Произошла ошибка при скачивании.**\nПричина: `{e}`")
    finally:
        session_key = make_session_key(cq.message)
        from database import _load_json, _save_json, SESSIONS_FILE
        sessions = _load_json(SESSIONS_FILE)
        sessions.pop(session_key, None)
        _save_json(SESSIONS_FILE, sessions)
        
        if status_message and "ошибка" not in status_message.text.lower():
             await status_message.delete()

async def handle_again(cq: CallbackQuery, session: dict):
    """Handles the 'again' button, resending the format selection."""
    link_type = session.get('type')
    title = session.get('title')
    author = session.get('author')
    
    if link_type == 'video':
        keyboard = format_video_keyboard(session['info'])
        new_msg = await cq.message.reply_photo(
            session['info'].get('thumbnail'),
            caption=f"**{title}**\n__{author}__",
            reply_markup=keyboard
        )
    else: # audio
        keyboard = format_audio_keyboard()
        new_msg = await cq.message.reply_text(
            f"**{title}**\n__{author}__",
            reply_markup=keyboard
        )
    
    new_session_key = make_session_key(new_msg)
    update_session(new_session_key, session)
    
    await cq.message.delete()
