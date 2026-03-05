import asyncio
import time
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, PROXY_CONFIG

if PROXY_CONFIG and PROXY_CONFIG.get("scheme"):
    app = Client(
        "ytbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        proxy=PROXY_CONFIG
    )
else:
    app = Client(
        "ytbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )


_EDIT_LOCK = asyncio.Lock()
_last_edit_time = 0.0
RATE_LIMIT = 0.5  # seconds

async def safe_edit_text(message, text, *args, **kwargs):
    """
    Edits a message, respecting a global rate limit to avoid flood waits.
    """
    global _last_edit_time
    async with _EDIT_LOCK:
        now = time.monotonic()
        elapsed = now - _last_edit_time
        if elapsed < RATE_LIMIT:
            await asyncio.sleep(RATE_LIMIT - elapsed)

        try:
            await message.edit_text(text, *args, **kwargs)
        except Exception:
            pass
        finally:
            _last_edit_time = time.monotonic()
