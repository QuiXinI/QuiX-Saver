import asyncio
import os
import glob
import time
import logging
import requests
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core import app, safe_edit_text
from database import get_session, update_session, get_user, update_user
from utils import make_session_key, format_video_keyboard, format_audio_keyboard, get_ydl, check_blacklist

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = "downloads"
ACTIVITY_LOG_FILE = "activity.log"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Logging ---

def log_activity(user_id, username, url, format_choice, file_size_mb):
    """Logs user download activity."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_message = (
        f"[{timestamp}] User: {user_id} (@{username if username else 'N/A'}), "
        f"URL: {url}, Format: {format_choice}, Size: {file_size_mb:.2f} MB\n"
    )
    with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_message)

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
        
        if "ошибка" not in status_message.text.lower():
             await status_message.delete()


async def handle_video_download(cq, session, data, status_message, loop, last_status):
    res = int(data.split(':')[1])
    title = session['title']
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{title}__{res}p.mp4")

    opts = {
        'format': f"bestvideo[ext=mp4][height<={res}]+bestaudio[ext=mp4]/best[ext=mp4][height<={res}]",
        'merge_output_format': 'mp4',
        'outtmpl': out_tmpl,
        'progress_hooks': [lambda d: _progress_hook(d, loop, status_message, last_status)],
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }

    ydl = get_ydl(opts)
    await loop.run_in_executor(None, lambda: ydl.download([session['url']]))
    
    file_size_mb = os.path.getsize(out_tmpl) / (1024 * 1024)
    log_activity(cq.from_user.id, cq.from_user.username, session['url'], f"video_{res}p", file_size_mb)

    await safe_edit_text(status_message, "🚀 Отправка...")
    await cq.message.reply_video(
        out_tmpl,
        caption=f"**{title}**\n__{session['author']}__",
        supports_streaming=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Скачать еще", callback_data="again")]]),
        progress=_send_progress,
        progress_args=(status_message, last_status, loop)
    )
    os.remove(out_tmpl)

async def handle_music_download(cq, session, data, status_message, loop, last_status):
    fmt = data.split(':')[1]
    title = session['title']
    base_path = os.path.join(DOWNLOAD_DIR, title)
    out_tmpl = base_path + '.%(ext)s'

    opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_tmpl,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': fmt, 'preferredquality': '0'}, {'key': 'FFmpegMetadata'}],
        'progress_hooks': [lambda d: _progress_hook(d, loop, status_message, last_status)],
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    if "yandex" in session['url']:
        opts['cookiesfrombrowser'] = ('firefox',)

    await loop.run_in_executor(None, lambda: get_ydl(opts).download([session['url']]))
    
    audio_file = next((f for f in glob.glob(base_path + '.*') if f.endswith(f'.{fmt}')), None)
    if not audio_file:
        raise FileNotFoundError("Downloaded audio file not found.")

    file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
    log_activity(cq.from_user.id, cq.from_user.username, session['url'], f"audio_{fmt}", file_size_mb)

    thumb_path = await download_thumbnail(session.get('info'), base_path)

    await safe_edit_text(status_message, "🚀 Отправка...")
    await cq.message.reply_audio(
        audio_file,
        caption=f"**{title}**\n__{session['author']}__ 🎧",
        title=title,
        performer=session['author'],
        thumb=thumb_path,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Скачать еще", callback_data="again")]]),
        progress=_send_progress,
        progress_args=(status_message, last_status, loop)
    )
    
    for f in glob.glob(base_path + '.*'):
        os.remove(f)

async def handle_video_to_audio_download(cq, session, status_message, loop, last_status):
    title = session['title']
    base_path = os.path.join(DOWNLOAD_DIR, title)
    out_tmpl = base_path + '.%(ext)s'

    opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_tmpl,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'opus', 'preferredquality': '0'}],
        'progress_hooks': [lambda d: _progress_hook(d, loop, status_message, last_status)],
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }

    await loop.run_in_executor(None, lambda: get_ydl(opts).download([session['url']]))
    
    audio_file = next((f for f in glob.glob(base_path + '.*') if f.endswith('.opus')), None)
    if not audio_file:
        raise FileNotFoundError("Converted audio file not found.")

    file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
    log_activity(cq.from_user.id, cq.from_user.username, session['url'], "video_to_audio_opus", file_size_mb)

    thumb_path = await download_thumbnail(session.get('info'), base_path)

    await safe_edit_text(status_message, "🚀 Отправка...")
    await cq.message.reply_audio(
        audio_file,
        caption=f"**{title}**\n__{session['author']}__ 🎧",
        title=title,
        performer=session['author'],
        thumb=thumb_path,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Скачать еще", callback_data="again")]]),
        progress=_send_progress,
        progress_args=(status_message, last_status, loop)
    )
    
    for f in glob.glob(base_path + '.*'):
        os.remove(f)

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

async def download_thumbnail(info: dict, base_path: str) -> str | None:
    """Downloads a thumbnail and returns its path."""
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
