import os
import json
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Proxy settings
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true"
if PROXY_ENABLED:
    PROXY_CONFIG = {
        "scheme": os.getenv("PROXY_SCHEME"),
        "hostname": os.getenv("PROXY_HOSTNAME"),
        "port": int(os.getenv("PROXY_PORT")),
        "username": os.getenv("PROXY_USERNAME", ""),
        "password": os.getenv("PROXY_PASSWORD", ""),
    }
else:
    PROXY_CONFIG = None

# Load other configs from JSON
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Constants
OWNER_ID = CONFIG.get("owner_id")
LOG_CHANNEL = CONFIG.get("log_channel")
SUPPORT_CHAT = CONFIG.get("support_chat")
DEFAULT_LANGUAGE = CONFIG.get("default_language", "en")
LANGUAGES = CONFIG.get("languages", {"en": "English", "ru": "Русский"})
