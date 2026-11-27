import os
import json
import hashlib
import shutil

USERS_FILE = "users.json"
BACKUP_USERS_FILE = os.path.join("workspaces", "users_backup.json")
WORKSPACES_DIR = "workspaces"
MASTER_RECOVERY_KEY = "TECHNKA2026"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _load_users() -> dict:
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            pass

    if os.path.exists(BACKUP_USERS_FILE):
        try:
            with open(BACKUP_USERS_FILE, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
                if isinstance(backup_data, dict) and backup_data:
                    with open(USERS_FILE, "w", encoding="utf-8") as out:
                        json.dump(backup_data, out, indent=2)
                    return backup_data
        except Exception:
            pass

    return {}


def _save_users(users: dict) -> None:
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    with open(BACKUP_USERS_FILE, "w", encoding="utf-8") as bf:
        json.dump(users, bf, indent=2)


def register_user(username: str, password: str, role: str = "viewer", employee_name: str = ""):
    clean_user = (username or "").strip().lower()
    if not clean_user or not clean_user.isalnum():
        return False, "Username must contain only letters and numbers."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."

    users = _load_users()
    if clean_user in users:
        return False, "Username already exists."

    has_admin = any(u.get("role") == "admin" for u in users.values())
    assigned_role = "admin" if not has_admin else (role if role in ("admin", "viewer") else "viewer")

    salt = os.urandom(8).hex()
    users[clean_user] = {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "role": assigned_role,
        "employee_name": (employee_name or "").strip(),
    }
    _save_users(users)
    os.makedirs(get_user_workspace(clean_user), exist_ok=True)
    return True, f"Account permanently saved with role: {assigned_role.upper()}"


def authenticate_user(username: str, password: str):
    clean_user = (username or "").strip().lower()
    users = _load_users()
    user_data = users.get(clean_user)
    if not user_data:
        return False, None

    salt = user_data.get("salt")
    stored_hash = user_data.get("password_hash") or user_data.get("hash") or user_data.get("password")

    is_valid = False
    if salt and stored_hash:
        is_valid = _hash_password(password, salt) == stored_hash
    elif stored_hash and not salt:
        # Legacy / plain or un-salted fallback: upgrade on successful login
        plain_sha = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        if password == stored_hash or plain_sha == stored_hash:
            is_valid = True
            new_salt = os.urandom(8).hex()
            user_data["salt"] = new_salt
            user_data["password_hash"] = _hash_password(password, new_salt)
            users[clean_user] = user_data
            _save_users(users)

    if is_valid:
        role = user_data.get("role", "admin")
        emp_name = user_data.get("employee_name", "")
        return True, {"username": clean_user, "role": role, "employee_name": emp_name}
    return False, None


def reset_password(username: str, verification_input: str, new_password: str):
    clean_user = (username or "").strip().lower()
    users = _load_users()
    user_data = users.get(clean_user)
    if not user_data:
        return False, "Username not found."
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters."

    saved_emp_name = (user_data.get("employee_name") or "").strip().lower()
    verify_clean = (verification_input or "").strip().lower()

    is_emp_match = bool(saved_emp_name and verify_clean == saved_emp_name)
    is_master_match = verify_clean == MASTER_RECOVERY_KEY.lower()
    is_username_only_fallback = (not saved_emp_name) and (verify_clean == clean_user)

    if not (is_emp_match or is_master_match
