import os
import json
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
USERS_FILE = os.path.join(BASE_DIR, "users.json")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Ensure users.json exists
if not os.path.isfile(USERS_FILE):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

load_dotenv(override=True)
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("ENV vars missing")
    exit(1)

app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# Helper to track users
async def track_user(user_id: int):
    with open(USERS_FILE, 'r+', encoding='utf-8') as f:
        users = json.load(f)
        if user_id not in users:
            users.append(user_id)
            f.seek(0)
            json.dump(users, f, ensure_ascii=False, indent=2)
            f.truncate()


def get_ydl(opts):
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
        label = CATEGORY_LABELS.get(h, f"{h}p {'📺' if h<720 else '🖥'}")
        row.append(InlineKeyboardButton(label, callback_data=f"video:{h}"))
        if len(row) == 2:
            kb.append(row); row=[]
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("🎧 Только звук", callback_data="audio")])
    return InlineKeyboardMarkup(kb)

@app.on_message(filters.command("start"))
async def start_cmd(_, msg):
    await track_user(msg.from_user.id)
    await msg.reply_text("Привет! Отправь ссылку на YouTube.")

@app.on_message(filters.regex(r"https?://(www\.)?youtu"))
async def handle_link(_, msg):
    await track_user(msg.from_user.id)
    url = msg.text.strip()
    info = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: get_ydl({'quiet': True, 'skip_download': True}).extract_info(url, False)
    )
    title = ''.join(c for c in info.get('title','') if c.isalnum() or c in (' ','.','_','-')).strip()
    author = info.get('uploader','Unknown')
    kb = await format_keyboard(info)
    await msg.reply_photo(info.get('thumbnail'), caption=f"{title} - {author}", reply_markup=kb)
    user_data[msg.from_user.id] = {'url': url,'info':info,'title':title,'author':author}

@app.on_callback_query()
async def cb_handler(_, cq: CallbackQuery):
    await track_user(cq.from_user.id)
    data = cq.data; uid = cq.from_user.id
    sess = user_data.get(uid)
    if not sess:
        return await cq.answer("Сессия не найдена", show_alert=True)
    await cq.message.edit_reply_markup(None)

    url,title,author = sess['url'],sess['title'],sess['author']
    info = sess['info']
    status = await cq.message.reply_text("📲 Скачивание...")
    btn_again=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Другой формат",callback_data="again")]])

    if data.startswith('video:'):
        res=int(data.split(':')[1])
        out=os.path.join(DOWNLOAD_DIR,f"{title}_{res}p.mp4")
        opts={'format':f"bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]/best[ext=mp4]",
              'quiet':True,'outtmpl':out,'merge_output_format':'mp4'}
        await asyncio.get_event_loop().run_in_executor(None,lambda: get_ydl(opts).download([url]))
        await status.edit_text("🚀 Отправка...")
        async def progress(cur,tot):
            pct=int(cur*100/tot) if tot else 0
            try: await status.edit_text(f"🚀 Отправка... {pct}%")
            except: pass
        await cq.message.reply_video(out,caption=f"{title} - {author} 🖥",supports_streaming=True,
                                     reply_markup=btn_again,progress=progress)
        os.remove(out)
    elif data=='audio':
        base=os.path.join(DOWNLOAD_DIR,title)
        opts={'format':'bestaudio/best','outtmpl':base+'.%(ext)s','quiet':True,
              'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'opus','preferredquality':'0'}]}
        await asyncio.get_event_loop().run_in_executor(None,lambda: get_ydl(opts).download([url]))
        opus=next(f for f in glob.glob(base+'.*') if f.endswith('.opus'))
        thumb=None
        if info.get('thumbnail'):
            thumb=base+'.jpg'
            r=requests.get(info['thumbnail'],timeout=10)
            if r.ok: open(thumb,'wb').write(r.content)
            else: thumb=None
        await status.edit_text("🚀 Отправка...")
        await cq.message.reply_audio(opus,caption=f"{title} - {author} 🎧",title=title,
                                     performer=author,thumb=thumb,reply_markup=btn_again)
        for f in glob.glob(base+'.*'): os.remove(f)
    elif data=='again':
        await status.delete()
        await cq.message.reply_text(f"{title} - {author}",reply_markup=await format_keyboard(info))
        return
    await status.delete()

if __name__ == '__main__':
    app.run()