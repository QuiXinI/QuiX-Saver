import os
import json
import asyncio
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv(override=True)
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
MESSAGE_FILE = os.path.join(BASE_DIR, "mass_sent.txt")

async def broadcast():
    # Read message to send
    if not os.path.isfile(MESSAGE_FILE):
        print(f"Message file not found: {MESSAGE_FILE}")
        return
    with open(MESSAGE_FILE, 'r', encoding='utf-8') as mf:
        message = mf.read().strip()
    if not message:
        print("Message file is empty.")
        return

    app = Client("ytbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    async with app:
        if not os.path.isfile(USERS_FILE):
            print(f"Users file not found: {USERS_FILE}")
            return
        with open(USERS_FILE, 'r', encoding='utf-8') as uf:
            users = json.load(uf)
        for uid in users:
            try:
                await app.send_message(uid, message)
            except Exception as e:
                print(f"Failed to send to {uid}: {e}")

if __name__ == '__main__':
    asyncio.run(broadcast())