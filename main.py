import os
import logging
import yt_dlp
import asyncio
import glob
import requests
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    144: "144p 📺", 240: "240p 📺", 360: "360p 📺",
    480: "480p 📺", 720: "720p 🖥", 1080: "1080p 🖥",
    1440: "QHD 🖥", 2160: "4K 🖥"
}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")
assert os.path.isfile(COOKIES_FILE), f"Cookies file not found: {COOKIES_FILE}"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

load_dotenv()
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("ENV vars missing")
    exit(1)

app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

def get_ydl(opts):
    """Helper to create a YoutubeDL with cookies."""
    default = {'cookiefile': COOKIES_FILE}
    default.update(opts)
    return yt_dlp.YoutubeDL(default)

async def format_keyboard(info):
    kb, row = [], []
    seen = set()
    for f in sorted(info['formats'], key=lambda x: (x.get('height') or 0), reverse=True):
        h = f.get('height')
        if not h or h in seen:
            continue
        seen.add(h)
        if h in CATEGORY_LABELS:
            label = CATEGORY_LABELS[h]
        else:
            icon = '📺' if h < 720 else '🖥'
            label = f"{h}p {icon}"
        row.append(InlineKeyboardButton(label, callback_data=f"video:{h}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🎧 Только звук", callback_data="audio")])
    return InlineKeyboardMarkup(kb)

@app.on_message(filters.command("start"))
async def start_cmd(_, msg):
    await msg.reply_text("Привет! Отправь ссылку на YouTube.")

@app.on_message(filters.regex(r"https?://(www\.)?youtu"))
async def handle_link(_, msg):
    url = msg.text.strip()
    # Extract info with cookies
    info = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: get_ydl({'quiet': True, 'skip_download': True}).extract_info(url, False)
    )
    title = ''.join(c for c in info.get('title', '') if c.isalnum() or c in (' ', '.', '_', '-')).strip()
    author = info.get('uploader', 'Unknown')
    kb = await format_keyboard(info)
    await msg.reply_photo(info.get('thumbnail'), caption=f"{title} - {author}", reply_markup=kb)
    user_data[msg.from_user.id] = {'url': url, 'info': info, 'title': title, 'author': author}

@app.on_callback_query()
async def cb_handler(_, cq: CallbackQuery):
    data = cq.data; uid = cq.from_user.id
    sess = user_data.get(uid)
    if not sess:
        return await cq.answer("Сессия не найдена", show_alert=True)
    await cq.message.edit_reply_markup(None)

    url = sess['url']; info = sess['info']
    title = sess['title']; author = sess['author']
    status = await cq.message.reply_text("📲 Скачивание...")
    btn_again = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Другой формат", callback_data="again")]])

    if data.startswith('video:'):
        res = int(data.split(':')[1])
        out = os.path.join(DOWNLOAD_DIR, f"{title}_{res}p.mp4")
        opts = {
            'format': f"bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]/best[ext=mp4]",
            'quiet': True,
            'outtmpl': out,
            'merge_output_format': 'mp4'
        }
        await asyncio.get_event_loop().run_in_executor(None, lambda: get_ydl(opts).download([url]))
        await status.edit_text("🚀 Отправка...")

        async def progress(current, total):
            pct = int(current*100/total) if total else 0
            try: await status.edit_text(f"🚀 Отправка... {pct}%")
            except: pass

        await cq.message.reply_video(out, caption=f"{title} - {author} 🖥", supports_streaming=True,
                                       reply_markup=btn_again, progress=progress)
        os.remove(out)

    elif data == 'audio':
        base = os.path.join(DOWNLOAD_DIR, title)
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': base + '.%(ext)s',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '0'
            }]
        }
        await asyncio.get_event_loop().run_in_executor(None, lambda: get_ydl(opts).download([url]))
        opus_file = next(f for f in glob.glob(base + '.*') if f.endswith('.opus'))
        thumb_path = None
        if info.get('thumbnail'):
            thumb_path = base + '.jpg'
            r = requests.get(info['thumbnail'], timeout=10)
            if r.ok:
                with open(thumb_path, 'wb') as f: f.write(r.content)
            else:
                thumb_path = None
        await status.edit_text("🚀 Отправка...")
        await cq.message.reply_audio(opus_file, caption=f"{title} - {author} 🎧",
                                     title=title, performer=author, thumb=thumb_path,
                                     reply_markup=btn_again)
        for f in glob.glob(base + '.*'): os.remove(f)

    elif data == 'again':
        await status.delete()
        kb = await format_keyboard(info)
        await cq.message.reply_text(f"{title} - {author}", reply_markup=kb)
        return

    await status.delete()

if __name__ == '__main__':
    app.run()
