import os
import glob
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core import safe_edit_text
from utils import get_ydl, _progress_hook, _send_progress, log_activity, download_thumbnail

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def handle_video_download(cq, session, data, status_message, loop, last_status):
    height_str = data.split(':')[1]
    title = session['title']

    try:
        target_height = int("".join(filter(str.isdigit, height_str)))
    except ValueError:
        await safe_edit_text(status_message, f"❌ **Неверный формат: {height_str}**")
        return

    all_formats = session.get('info', {}).get('formats', [])
    if not all_formats:
        await safe_edit_text(status_message, "❌ **Информация о форматах видео не найдена.**")
        return

    candidate_formats = [
        f for f in all_formats
        if isinstance(f, dict) and f.get('height') == target_height and f.get('vcodec') != 'none'
    ]

    if not candidate_formats:
        await safe_edit_text(status_message, f"❌ **Не удалось найти подходящий формат для разрешения {height_str}.**")
        return

    # Select the best candidate by bitrate from the cached info
    best_format = sorted(candidate_formats, key=lambda x: x.get('tbr', 0), reverse=True)[0]
    format_id = best_format['format_id']

    # Use a robust format spec: try to merge with best audio, but fall back to the format itself.
    format_spec = f"{format_id}+bestaudio/{format_id}"

    resolution = height_str
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{title}__{resolution}.%(ext)s")

    opts = {
        'format': format_spec,
        'merge_output_format': 'mp4',
        'outtmpl': out_tmpl,
        'progress_hooks': [lambda d: _progress_hook(d, loop, status_message, last_status)],
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }

    ydl = get_ydl(opts)
    # Download using the URL, but with the specifically chosen format_id.
    # This lets yt-dlp fetch fresh info but directs it to the correct format.
    await loop.run_in_executor(None, lambda: ydl.download([session['url']]))
    
    downloaded_file = next(glob.iglob(os.path.join(DOWNLOAD_DIR, f"{title}__{resolution}.*")), None)
    if not downloaded_file:
        raise FileNotFoundError("Downloaded video file not found.")

    file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
    log_activity(cq.from_user.id, cq.from_user.username, session['url'], f"video_{resolution}", file_size_mb)

    await safe_edit_text(status_message, "🚀 Отправка...")
    await cq.message.reply_video(
        downloaded_file,
        caption=f"**{title}**\n__{session['author']}__",
        supports_streaming=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Скачать еще", callback_data="again")]]),
        progress=_send_progress,
        progress_args=(status_message, last_status, loop)
    )
    os.remove(downloaded_file)

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
