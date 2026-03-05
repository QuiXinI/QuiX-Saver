import asyncio

async def main():
    from core import app

    print("Bot is starting...")
    await app.start()
    print("Bot is running. Press Ctrl+C to stop.")
    from pyrogram import idle
    await idle()
    await app.stop()
    print("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass