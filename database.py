import json
import os
from threading import Lock

DATA_DIR = "data"
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")

os.makedirs(DATA_DIR, exist_ok=True)

_lock = Lock()

def _load_json(file_path, default_factory=dict):
    """Loads a JSON file."""
    with _lock:
        if not os.path.exists(file_path):
            return default_factory()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return default_factory()

def _save_json(file_path, data):
    """Saves data to a JSON file."""
    with _lock:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# --- User Management ---

def get_user(user_id):
    """Gets a user's data."""
    users = _load_json(USERS_FILE)
    return users.get(str(user_id))

def update_user(user_id, data):
    """Creates or updates a user's data."""
    users = _load_json(USERS_FILE)
    users[str(user_id)] = data
    _save_json(USERS_FILE, users)

def get_all_users():
    """Returns all users."""
    return _load_json(USERS_FILE)

# --- Session Management ---

def get_session(user_id):
    """Gets a user's session data."""
    sessions = _load_json(SESSIONS_FILE)
    return sessions.get(str(user_id))

def update_session(user_id, data):
    """Creates or updates a user's session."""
    sessions = _load_json(SESSIONS_FILE)
    sessions[str(user_id)] = data
    _save_json(SESSIONS_FILE, sessions)

# --- Blacklist Management ---

def is_blacklisted(user_id):
    """Checks if a user is in the blacklist."""
    blacklist = _load_json(BLACKLIST_FILE, default_factory=dict)
    return str(user_id) in blacklist

def add_to_blacklist(user_id):
    """Adds a user to the blacklist."""
    blacklist = _load_json(BLACKLIST_FILE, default_factory=dict)
    user_id_str = str(user_id)
    if user_id_str not in blacklist:
        blacklist[user_id_str] = {"id": user_id}
        _save_json(BLACKLIST_FILE, blacklist)

def remove_from_blacklist(user_id):
    """Removes a user from the blacklist."""
    blacklist = _load_json(BLACKLIST_FILE, default_factory=dict)
    user_id_str = str(user_id)
    if user_id_str in blacklist:
        del blacklist[user_id_str]
        _save_json(BLACKLIST_FILE, blacklist)
