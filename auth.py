import os
import json
import hashlib
import secrets
import shutil

USERS_FILE = "users.json"
WORKSPACES_DIR = "workspaces"

def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${hashed}"

def _verify_password(password, stored_hash):
    salt, _ = stored_hash.split("$")
    return _hash_password(password, salt) == stored_hash

def register_user(username, password):
    username = username.strip().lower()
    if not username.isalnum():
        return False, "Username must contain only letters and numbers."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    users = _load_users()
    if username in users:
        return False, "Username already exists."

    users[username] = {"password_hash": _hash_password(password)}
    _save_users(users)
    get_user_workspace(username)  # Initialize private folder
    return True, "Account created! You can now log in."

def authenticate_user(username, password):
    username = username.strip().lower()
    users = _load_users()
    if username not in users:
        return False
    return _verify_password(password, users[username]["password_hash"])

def get_user_workspace(username):
    """Returns a private folder path exclusive to the logged-in user."""
    safe_user = "".join(c for c in username.lower() if c.isalnum())
    user_dir = os.path.join(WORKSPACES_DIR, safe_user)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def delete_user_data(username):
    """Permanently wipes all private data for a specific user."""
    user_dir = get_user_workspace(username)
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        os.makedirs(user_dir, exist_ok=True)