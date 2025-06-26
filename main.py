import os
import json
import logging
import asyncio
import glob
import time
import re
import requests
import yt_dlp
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

AUDIO_FORMATS = {
    "mp3": "👎 MP3 👎",
    "opus": "✨ Opus ✨",
    "flac": "👾 FLAC 👾",
    "wav": "🤓 WAV 🤓"
}

# Quality labels for video formats
CATEGORY_LABELS = {
    144: "144p 📺",
    240: "240p 📺",
    360: "360p 📺",
    480: "480p 📺",
    720: "720p 🖥",
    1080: "1080p 🖥",
    1440: "QHD 🖥",
    2160: "4K 🖥"
}

# Directories and files
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    _cfg = json.load(f)
    COOLDOWN_TIME = float(_cfg.get('edit_cooldown', 0.5))
    SESSIONS_FILE = os.path.join(BASE_DIR, _cfg.get('sessions_file', "sessions.json"))
    USERS_FILE = os.path.join(BASE_DIR, _cfg.get('users_file', "users.json"))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, _cfg.get('download_dir', "downloads"))

last_status = {"text": None}
_last_edit_ts = 0.0

# Ensure required files and directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
for path, default in (
    (USERS_FILE, []),
    (SESSIONS_FILE, {})
):
    if not os.path.isfile(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

# Load environment variables
load_dotenv(override=True)
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("ENV vars missing")
    exit(1)

# Initialize bot client
token = BOT_TOKEN
app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=token)

# Session management on disk
def load_sessions():
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_sessions(sessions):
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)

def track_user(user_id: int):
    with open(USERS_FILE, 'r+', encoding='utf-8') as f:
        users = json.load(f)
        if user_id not in users:
            users.append(user_id)
            f.seek(0)
            json.dump(users, f, ensure_ascii=False, indent=2)
            f.truncate()

# YoutubeDL helper
def get_ydl(opts):
    default = {}
    default.update(opts)
    return yt_dlp.YoutubeDL(default)

# Helper: format keyboard for video
def format_keyboard(info):
    kb, row, seen = [], [], set()
    for f in sorted(info['formats'], key=lambda x: x.get('height') or 0, reverse=True):
        height = f.get('height')
        if not height or height in seen:
            continue
        seen.add(height)
        label = CATEGORY_LABELS.get(
            height, f"{height}p {'📺' if height < 720 else '🖥'}"
        )
        row.append(InlineKeyboardButton(label, callback_data=f"video:{height}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🎧 Только звук", callback_data="audio")])
    return InlineKeyboardMarkup(kb)

# Helper: format keyboard for audio formats
def format_audio_keyboard():
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

@app.on_message(filters.command("start"))
async def start_cmd(_, msg):
    track_user(msg.from_user.id)
    await msg.reply_text("Привет! Отправь ссылку на YouTube или Яндекс.Музыку.")

@app.on_message(filters.regex(r"https?://(www\.)?youtu"))
async def handle_youtube_link(_, msg):
    track_user(msg.from_user.id)
    url = msg.text.strip()

    # Function to get formats
    def fetch_formats(url: str):
        ydl_opts = {
            'quiet': False,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, fetch_formats, url)
    except Exception as e:
        logger.error(f"Error fetching formats: {e}")
        if "Sign in to confirm your age" in str(e):
            e = "видео имеет ограничения возраста"
        elif "This video is not available" in str(e):
            e = "видео не доступно на территории РФ и Германии"
        elif "copyright" in str(e):
            e = "видео закопирайчено, не можем скачать"
        return await msg.reply_text(f"❌ Ошибка при получении форматов: {e} ❌")

    title = ''.join(
        c for c in info.get('title','')
        if c.isalnum() or c in (' ','.','_','-')
    ).strip()
    author = info.get('uploader','Unknown')

    sessions = load_sessions()
    sessions[str(msg.from_user.id)] = {
        'url': url,
        'info': info,
        'title': title,
        'author': author,
        'type': 'video'
    }
    save_sessions(sessions)

    kb = format_keyboard(info)
    await msg.reply_photo(
        info.get('thumbnail'),
        caption=f"{title} - {author}",
        reply_markup=kb
    )

@app.on_message(filters.regex(r"https?://(music\.youtube\.com|music\.yandex\.ru)"))
async def handle_music_link(_, msg):
    track_user(msg.from_user.id)
    url = msg.text.strip()

    def fetch_info(url: str):
        ydl_opts = {'quiet': False, 'skip_download': True}
        if "yandex" in url:
            ydl_opts['cookiesfrombrowser'] = ('firefox',)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, fetch_info, url)
    except Exception as e:
        logger.error(f"Error fetching info: {e}")
        return await msg.reply_text(f"❌ Ошибка при получении информации: {e} ❌")

    # Extract and clean the title and author
    full_title = info.get('title', '')
    title = full_title.split(' - ')[0].strip()

    # Extract author information
    author = info.get('artist') or info.get('uploader', 'Unknown')

    # If the author is part of the title, remove it
    if author in full_title:
        title = full_title.replace(author, '').strip().replace('  ', ' ').strip('- ')

    sessions = load_sessions()
    sessions[str(msg.from_user.id)] = {
        'url': url,
        'info': info,
        'title': title,
        'author': author,
        'type': 'audio'
    }
    save_sessions(sessions)

    kb = format_audio_keyboard()
    await msg.reply_text(
        f"{title} - {author}",
        reply_markup=kb
    )

@app.on_callback_query()
async def cb_handler(_, cq: CallbackQuery):
    track_user(cq.from_user.id)
    sessions = load_sessions()
    sess = sessions.get(str(cq.from_user.id))
    if not sess:
        return await cq.answer("Сессия не найдена", show_alert=True)

    await cq.message.edit_reply_markup(None)
    url = sess['url']; title = sess['title']; author = sess['author']; info = sess['info']; link_type = sess.get('type')

    status = await cq.message.reply_text("📥 Скачивание...")
    btn_again = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Другой формат", callback_data="again")]
    ])

    loop = asyncio.get_running_loop()
    last_status = {"text": None}
    data = cq.data

    if data.startswith('video:') and link_type == 'video':
        res = int(data.split(':')[1])
        out = os.path.join(DOWNLOAD_DIR, f"{title}_{res}p.mp4")

        def download_hook(d):
            global _last_edit_ts
            now = time.monotonic()
            if now - _last_edit_ts < COOLDOWN_TIME:
                return
            status_text = None
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                cur = d.get('downloaded_bytes', 0)
                pct = int(cur * 100 / total) if total else 0
                status_text = f"📥 Скачивание... {pct}%"
            if status_text and status_text != last_status.get("text"):
                last_status["text"] = status_text
                _last_edit_ts = now
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        opts = {
            'format': f"bestvideo[ext=mp4][height<={res}]+bestaudio/best",
            'merge_output_format': 'mp4',
            'quiet': False,
            'outtmpl': out,
            'progress_hooks': [download_hook],
        }

        ydl = get_ydl(opts)
        info = ydl.extract_info(url, download=False)
        await loop.run_in_executor(None, lambda: ydl.download([url]))

        caption = f"{title} — {author}\n"
        def send_progress(cur, tot):
            pct = int(cur * 100 / tot) if tot else 0
            status_text = f"🚀 Отправка... {pct}%"
            if status_text != last_status["text"]:
                last_status["text"] = status_text
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        await cq.message.reply_video(
            out,
            caption=caption,
            supports_streaming=True,
            reply_markup=btn_again,
            progress=send_progress
        )
        os.remove(out)

    elif data.startswith('audioformat:') and link_type == 'audio':
        fmt = data.split(':')[1]
        base = os.path.join(DOWNLOAD_DIR, title)
        postprocessors = []
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': fmt,
            'preferredquality': '0',
        })
        postprocessors.append({'key': 'FFmpegMetadata'})

        opts = {
            'format': 'bestaudio/best',
            'outtmpl': base + '.%(ext)s',
            'quiet': False,
            'postprocessors': postprocessors,
            'progress_hooks': [
                lambda d: download_hook_shared(d, loop, status, last_status)
            ],
        }
        if "yandex" in url:
            opts['cookiesfrombrowser'] = ('firefox',)

        await loop.run_in_executor(None, lambda: get_ydl(opts).download([url]))
        audio_file = next(f for f in glob.glob(base + '.*') if f.endswith(f'.{fmt}'))

        thumb = None
        thumb_url = info.get('thumbnail') or info.get('thumbnails', [{}])[-1].get('url')
        if thumb_url:
            thumb = base + '.jpg'
            r = requests.get(thumb_url, timeout=10)
            if r.ok:
                open(thumb, 'wb').write(r.content)
            else:
                thumb = None

        def send_progress(cur, tot):
            pct = int(cur * 100 / tot) if tot else 0
            status_text = f"🚀 Отправка... {pct}%"
            if status_text != last_status["text"]:
                last_status["text"] = status_text
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        await status.edit_text("🚀 Отправка...")
        await cq.message.reply_audio(
            audio_file,
            caption=f"{title} - {author} 🎧",
            title=title,
            performer=author,
            thumb=thumb,
            reply_markup=btn_again,
            progress=send_progress
        )
        for f in glob.glob(base + '.*'):
            os.remove(f)

    elif data == 'audio' and link_type == 'video':
        def download_hook(d):
            global _last_edit_ts
            now = time.monotonic()
            if now - _last_edit_ts < COOLDOWN_TIME:
                return
            status_text = None
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                cur = d.get('downloaded_bytes', 0)
                pct = int(cur * 100 / total) if total else 0
                status_text = f"📥 Скачивание... {pct}%"
            if status_text and status_text != last_status.get("text"):
                last_status["text"] = status_text
                _last_edit_ts = now
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        base = os.path.join(DOWNLOAD_DIR, title)
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': base + '.%(ext)s',
            'quiet': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '0',
            }],
            'progress_hooks': [download_hook],
        }
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: get_ydl(opts).download([url])
        )
        opus_file = next(f for f in glob.glob(base + '.*') if f.endswith('.opus'))

        thumb = None
        thumb_url = info.get('thumbnail')
        if thumb_url:
            thumb = base + '.jpg'
            r = requests.get(thumb_url, timeout=10)
            if r.ok:
                open(thumb, 'wb').write(r.content)
            else:
                thumb = None

        def send_progress(cur, tot):
            pct = int(cur * 100 / tot) if tot else 0
            status_text = f"🚀 Отправка... {pct}%"
            if status_text != last_status["text"]:
                last_status["text"] = status_text
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        await status.edit_text("🚀 Отправка...")
        await cq.message.reply_audio(
            opus_file,
            caption=f"{title} - {author} 🎧",
            title=title,
            performer=author,
            thumb=thumb,
            reply_markup=btn_again,
            progress=send_progress
        )
        for f in glob.glob(base + '.*'):
            os.remove(f)

    elif data == 'again':
        await status.delete()
        if link_type == 'video':
            kb = format_keyboard(info)
            await cq.message.reply_text(f"{title} - {author}", reply_markup=kb)
        else:
            kb = format_audio_keyboard()
            await cq.message.reply_text(f"{title} - {author}", reply_markup=kb)
        return

    await status.delete()

# Shared download hook for audio formats
def download_hook_shared(d, loop, status, last_status):
    global _last_edit_ts
    now = time.monotonic()
    if now - _last_edit_ts < COOLDOWN_TIME:
        return
    status_text = None
    if d.get('status') == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        cur = d.get('downloaded_bytes', 0)
        pct = int(cur * 100 / total) if total else 0
        status_text = f"📥 Скачивание... {pct}%"
    if status_text and status_text != last_status.get("text"):
        last_status["text"] = status_text
        _last_edit_ts = now
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(status.edit_text(status_text))
        )

if __name__ == '__main__':
    try:
        app.start()
    except AttributeError as e:
        if 'BadMsgNotification' in str(e):
            logger.warning("Time sync issue detected, retrying start...")
            time.sleep(1)
            app.start()
        else:
            raise
