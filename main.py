import os
import json
import logging
import asyncio
import glob
import time

import requests

import yt_dlp
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
BASE_DIR     = os.path.abspath(os.path.dirname(__file__))
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    _cfg = json.load(f)
    COOLDOWN_TIME = float(_cfg.get('edit_cooldown', 0.5))
    COOKIES_FILE = os.path.join(BASE_DIR, _cfg.get('cookies_file', "cookies.txt"))
    SESSIONS_FILE = os.path.join(BASE_DIR, _cfg.get('sessions_file', "sessions.json"))
    USERS_FILE = os.path.join(BASE_DIR, _cfg.get('users_file', "users.json"))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, _cfg.get('download_dir', "downloads"))

last_status = {"text": None}
_last_edit_ts = 0.0

# Ensure required files and directories exist
assert os.path.isfile(COOKIES_FILE), f"Cookies file not found: {COOKIES_FILE}"
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
    # Track in users.json
    with open(USERS_FILE, 'r+', encoding='utf-8') as f:
        users = json.load(f)
        if user_id not in users:
            users.append(user_id)
            f.seek(0)
            json.dump(users, f, ensure_ascii=False, indent=2)
            f.truncate()

# Helper: create YoutubeDL instance
def get_ydl(opts):
    # default = {'cookiefile': COOKIES_FILE}
    default = {}
    # default = {'cookies-from-browser': 'chrome'}
    default.update(opts)
    return yt_dlp.YoutubeDL(default)

# Helper: format keyboard
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

@app.on_message(filters.command("start"))
async def start_cmd(_, msg):
    track_user(msg.from_user.id)
    await msg.reply_text("Привет! Отправь ссылку на YouTube.")

@app.on_message(filters.regex(r"https?://(www\.)?youtu"))
async def handle_link(_, msg):
    track_user(msg.from_user.id)
    url = msg.text.strip()

    # Функция для получения форматов
    def fetch_formats(url: str):
        # Получаем информацию о форматах без вывода в консоль
        ydl_opts = {
            'quiet': False,         # подавить вывод в консоль
            'skip_download': True, # не скачивать контент
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info вернёт словарь с ключом 'formats'
            return ydl.extract_info(url, download=False)

    # Используем уже запущенный event loop
    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, fetch_formats, url)
    except Exception as e:
        logger.error(f"Error fetching formats: {e}")
        if "Sign in to confirm your age" in str(e):
            e = "видео имеет ограничения возраста"
        elif "This video is not available" in str(e):
            e = "видео не доступно на территории РФ и Германии"
        elif "copyright" in e:
            e = "видео закопирайчено, не можем скачать"
        return await msg.reply_text(f"Ошибка при получении форматов: {e}")

    # Clean title and author
    title = ''.join(
        c for c in info.get('title','')
        if c.isalnum() or c in (' ','.','_','-')
    ).strip()
    author = info.get('uploader','Unknown')

    # Save session
    sessions = load_sessions()
    sessions[str(msg.from_user.id)] = {
        'url': url,
        'info': info,
        'title': title,
        'author': author
    }
    save_sessions(sessions)

    # Send keyboard
    kb = format_keyboard(info)
    await msg.reply_photo(
        info.get('thumbnail'),
        caption=f"{title} - {author}",
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
    url = sess['url']; title = sess['title']; author = sess['author']; info = sess['info']

    status = await cq.message.reply_text("📥 Скачивание...")
    btn_again = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Другой формат", callback_data="again")]]
    )

    loop = asyncio.get_running_loop()
    last_status = {"text": None}

    data = cq.data
    if data.startswith('video:'):
        res = int(data.split(':')[1])
        out = os.path.join(DOWNLOAD_DIR, f"{title}_{res}p.mp4")

        # прогресс-хук для yt-dlp
        def download_hook(d):
            """
            Hook for yt_dlp: edits the message in the chat no more frequently than COOLDOWN_TIME seconds.
            Expects global variables last_status, _last_edit_ts, loop, and status to be defined.
            """
            global _last_edit_ts

            # Calculate the interval since the last edit
            now = time.monotonic()
            if now - _last_edit_ts < COOLDOWN_TIME:
                return  # Exit if it's too soon to edit again

            status_text = None
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                cur = d.get('downloaded_bytes', 0)
                pct = int(cur * 100 / total) if total else 0
                status_text = f"📥 Скачивание... {pct}%"

            # If there is text and it's different from the last status, edit the message
            if status_text and status_text != last_status.get("text"):
                last_status["text"] = status_text
                _last_edit_ts = now

                # Schedule edit_text in the main loop
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
        width = info.get('width', 0)
        height = info.get('height', 0)
        duration = int(info.get('duration', 0))
        aspect = f"{width}:{height}"

        # скачиваем в треде
        await loop.run_in_executor(None, lambda: ydl.download([url]))

        caption = (
            f"{title} — {author}\n"
        )

        # прогресс отправки
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

    elif data == 'audio':
        # прогресс-хук для yt-dlp
        def download_hook(d):
            """
            Hook for yt_dlp: edits the message in the chat no more frequently than COOLDOWN_TIME seconds.
            Expects global variables last_status, _last_edit_ts, loop, and status to be defined.
            """
            global _last_edit_ts

            # Calculate the interval since the last edit
            now = time.monotonic()
            if now - _last_edit_ts < COOLDOWN_TIME:
                return  # Exit if it's too soon to edit again

            status_text = None
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                cur = d.get('downloaded_bytes', 0)
                pct = int(cur * 100 / total) if total else 0
                status_text = f"📥 Скачивание... {pct}%"

            # If there is text and it's different from the last status, edit the message
            if status_text and status_text != last_status.get("text"):
                last_status["text"] = status_text
                _last_edit_ts = now

                # Schedule edit_text in the main loop
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(status.edit_text(status_text))
                )

        # Download audio
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
        kb = format_keyboard(info)
        await cq.message.reply_text(f"{title} - {author}", reply_markup=kb)
        return

    await status.delete()

if __name__ == '__main__':
    app.run()
