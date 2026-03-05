import json
from typing import Dict, Any, List, Optional

USERS_FILE = 'users.json'
SESSIONS_FILE = 'sessions.json'


def _load_users() -> Dict[str, Any]:
    """Loads users from users.json, ensuring it's a dictionary."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(users: Dict[str, Any]):
    """Saves users to users.json."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Gets a user by their ID."""
    users = _load_users()
    return users.get(str(user_id))


def update_user(user_id: int, **kwargs):
    """Creates or updates a user's data."""
    users = _load_users()
    user_key = str(user_id)
    if user_key not in users:
        users[user_key] = {}
    users[user_key].update(kwargs)
    _save_users(users)


def is_blacklisted(user_id: int) -> bool:
    """Checks if a user is blacklisted."""
    user = get_user(user_id)
    return user.get('is_blacklisted', False) if user else False


def _load_sessions() -> Dict[str, List[Dict[str, Any]]]:
    """Loads all user sessions from sessions.json."""
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sessions(sessions: Dict[str, List[Dict[str, Any]]]):
    """Saves all user sessions to sessions.json."""
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=4)


def add_session(user_id: int, session_data: Dict[str, Any]):
    """Adds a new session to a user's session history."""
    sessions = _load_sessions()
    user_key = str(user_id)
    if user_key not in sessions:
        sessions[user_key] = []
    sessions[user_key].append(session_data)
    _save_sessions(sessions)


def get_session_by_message_id(user_id: int, message_id: int) -> Optional[Dict[str, Any]]:
    """Finds a session by its associated message_id for a specific user."""
    sessions = _load_sessions()
    user_sessions = sessions.get(str(user_id), [])
    for session in reversed(user_sessions):
        if session.get('message_id') == message_id:
            return session
    return None


def get_latest_session(user_id: int) -> Optional[Dict[str, Any]]:
    """Gets the most recent session for a user."""
    sessions = _load_sessions()
    user_sessions = sessions.get(str(user_id), [])
    if user_sessions:
        return user_sessions[-1]
    return None
