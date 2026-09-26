from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path

from common.paths import get_common_base_dir

USERS_FILE = get_common_base_dir() / "common" / "data" / "users.json"

ROLE_ADMIN = "admin"       
ROLE_OPERATOR = "operator"  
ROLES = (ROLE_ADMIN, ROLE_OPERATOR)

MIN_PASSWORD_LENGTH = 6


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _load_users() -> dict[str, dict[str, str]]:
    if not USERS_FILE.exists():
        return {}
    try:
        with USERS_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        
        return {}
    return data if isinstance(data, dict) else {}


def _save_users(users: dict[str, dict[str, str]]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
   
    fd, tmp_path = tempfile.mkstemp(
        dir=USERS_FILE.parent, prefix=USERS_FILE.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(users, file, indent=2)
        os.replace(tmp_path, USERS_FILE)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _seed_default_admin_if_empty() -> None:
    users = _load_users()
    if users:
        return
    salt = secrets.token_hex(16)
    users["Anil"] = {
        "salt": salt,
        "password_hash": _hash_password("06082003", salt),
        "role": ROLE_ADMIN,
    }
    _save_users(users)


def authenticate_user(username: str, password: str) -> tuple[bool, str, str]:
    _seed_default_admin_if_empty()
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return False, "Username and password are required.", ""

    users = _load_users()
    record = users.get(username)
    if record is None:
        return False, "Invalid username or password.", ""

    expected = record["password_hash"]
    actual = _hash_password(password, record["salt"])
    if actual != expected:
        return False, "Invalid username or password.", ""

    role = record.get("role", ROLE_OPERATOR)
    return True, username, role


def list_users() -> list[tuple[str, str]]:
    _seed_default_admin_if_empty()
    users = _load_users()
    return sorted((name, rec.get("role", ROLE_OPERATOR)) for name, rec in users.items())


def get_user_role(username: str) -> str | None:
    users = _load_users()
    record = users.get(username)
    return record.get("role", ROLE_OPERATOR) if record else None


def add_user(username: str, password: str, role: str = ROLE_OPERATOR) -> tuple[bool, str]:
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return False, "Username and password are required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if role not in ROLES:
        return False, "Invalid role."

    users = _load_users()
    if username.lower() in {name.lower() for name in users}:
        return False, "Username already exists."

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "role": role,
    }
    _save_users(users)
    role_label = "Admin" if role == ROLE_ADMIN else "Operator"
    return True, f'{role_label} "{username}" added.'


def delete_user(username: str, *, current_user: str) -> tuple[bool, str]:
    username = username.strip()
    users = _load_users()
    if username not in users:
        return False, "User not found."
    if username == current_user:
        return False, "You cannot delete the account you're currently logged in as."

    admin_count = sum(1 for rec in users.values() if rec.get("role", ROLE_OPERATOR) == ROLE_ADMIN)
    if users[username].get("role", ROLE_OPERATOR) == ROLE_ADMIN and admin_count <= 1:
        return False, "At least one Admin account must remain."
    if len(users) <= 1:
        return False, "At least one account must remain."

    role_label = "Admin" if users[username].get("role", ROLE_OPERATOR) == ROLE_ADMIN else "Operator"
    del users[username]
    _save_users(users)
    return True, f'{role_label} "{username}" removed.'