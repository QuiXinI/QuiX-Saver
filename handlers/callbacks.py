import logging
import asyncio
from pyrogram import filters
from pyrogram.types import CallbackQuery
from core import app
from database import get_session_by_message_id, get_latest_session
from handlers.download_logic import handle_video_download, handle_music_download, handle_video_to_audio_download
from handlers.youtube import youtube_handler
from handlers.yandex_music import yandex_music_handler
from handlers.youtube_music import youtube_music_handler

logger = logging.getLogger(__name__)

@app.on_callback_query()
async def callback_handler(client, cq: CallbackQuery):
    """Handles all callback queries."""
    user_id = cq.from_user.id
    message = cq.message
    data = cq.data

    session = get_session_by_message_id(user_id, message.id)
    if not session and data != "again":
        await cq.answer("⚠️ Сессия не найдена. Возможно, бот перезапускался. Пожалуйста, отправьте ссылку заново.", show_alert=True)
        return

    if session and session.get('user_id') != user_id:
        await cq.answer("⚠️ Вы не можете использовать кнопки для чужого запроса.", show_alert=True)
        return

    await cq.answer() # Acknowledge the callback

    if data == "again":
        latest_session = get_latest_session(user_id)
        if not latest_session:
            await message.edit_text("❌ Ваша история запросов пуста.")
            return
        
        url = latest_session.get('url')
        session_type = latest_session.get('type')
        
        # Re-trigger the appropriate handler, passing the original message to edit
        if session_type == 'youtube':
            await youtube_handler(client, message, url_override=url, user_id_override=user_id)
        elif session_type == 'yandex_music':
            await yandex_music_handler(client, message, url_override=url, user_id_override=user_id)
        elif session_type == 'youtube_music':
            await youtube_music_handler(client, message, url_override=url, user_id_override=user_id)
        else:
            await message.edit_text("❌ Не удалось определить тип последнего запроса.")
        return

    # --- Download Logic ---
    status_message = await message.edit_text("⏳ Запрос принят, начинаю обработку...")
    loop = asyncio.get_event_loop()
    last_status = {"text": ""}

    try:
        if data.startswith("video:"):
            await handle_video_download(cq, session, data, status_message, loop, last_status)
        elif data.startswith("audioformat:"):
            await handle_music_download(cq, session, data, status_message, loop, last_status)
        elif data == "audio":
            await handle_video_to_audio_download(cq, session, status_message, loop, last_status)
        else:
            await status_message.edit_text("❌ Неизвестный формат.")

    except FileNotFoundError:
        logger.error(f"File not found after download for session: {session.get('url')}")
        await status_message.edit_text("❌ **Ошибка:** Скачанный файл не найден на сервере.")
    except Exception as e:
        logger.error(f"Error during download callback for {session.get('url')}: {e}", exc_info=True)
        await status_message.edit_text(f"❌ **Произошла критическая ошибка:**\n`{e}`")
    finally:
        if status_message and not message.video and not message.audio:
            try:
                current_text = (await client.get_messages(chat_id=message.chat.id, message_ids=message.id)).text
                if current_text == status_message.text:
                    await status_message.delete()
            except Exception:
                pass
