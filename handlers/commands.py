from pyrogram import filters
from core import app
from database import update_user
from utils import check_blacklist

@app.on_message(filters.command("start"))
@check_blacklist
async def start_command(_, message):
    """Handles the /start command."""
    user_id = message.from_user.id

    from database import get_user
    if not get_user(user_id):
        update_user(user_id, {"id": user_id, "lang": "ru"}) # Default lang

    await message.reply_text(
        "👋 **Привет!**\n\n"
        "Я бот для скачивания видео и музыки. Просто отправь мне ссылку с YouTube или Яндекс.Музыки, и я помогу тебе её скачать.\n\n"
        "Канал разработчика: @quix_the_artist\n"
        "По вопросам и техническим @quidraa"
    )
