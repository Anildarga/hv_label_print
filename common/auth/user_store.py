from __future__ import annotations

from common.api_client import APIClientError, delete, get, post, set_bearer_token

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLES = (ROLE_ADMIN, ROLE_OPERATOR)
MIN_PASSWORD_LENGTH = 6


def authenticate_user(username: str, password: str) -> tuple[bool, str, str]:
    username = username.strip()
    if not username or not password:
        return False, "Username and password are required.", ""
    set_bearer_token(None)
    try:
        result = post(
            "/users/authenticate",
            {"username": username, "password": password},
        )
    except APIClientError as exc:
        if exc.status_code == 401:
            return False, "Invalid username or password.", ""
        raise
    role = str(result.get("role") or ROLE_OPERATOR)
    set_bearer_token(result.get("access_token"))
    return True, str(result.get("username") or username), role


def list_users() -> list[tuple[str, str]]:
    result = get("/users")
    return sorted(
        (str(user.get("username") or ""), str(user.get("role") or ROLE_OPERATOR))
        for user in result
    )


def get_user_role(username: str) -> str | None:
    target = username.strip().casefold()
    return next(
        (role for name, role in list_users() if name.casefold() == target),
        None,
    )


def add_user(
    username: str, password: str, role: str = ROLE_OPERATOR
) -> tuple[bool, str]:
    username = username.strip()
    password = password.strip()
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if role not in ROLES:
        return False, "Invalid role."

    try:
        post(
            "/users",
            {"username": username, "password": password, "role": role},
        )
    except APIClientError as exc:
        if exc.status_code == 409:
            return False, "Username already exists."
        if exc.status_code == 422:
            return False, "The server rejected the user details."
        raise
    role_label = "Admin" if role == ROLE_ADMIN else "Operator"
    return True, f'{role_label} "{username}" added.'


def delete_user(username: str, *, current_user: str) -> tuple[bool, str]:
    username = username.strip()
    if username.casefold() == current_user.casefold():
        return False, "You cannot delete the account you're currently logged in as."

    target = next(
        (
            user for user in get("/users")
            if str(user.get("username") or "").casefold() == username.casefold()
        ),
        None,
    )
    if target is None:
        return False, "User not found."
    user_id = target.get("id")
    if not user_id:
        raise APIClientError("Server returned a user without its database id.")
    try:
        delete(f"/users/{user_id}")
    except APIClientError as exc:
        if exc.status_code == 404:
            return False, "User not found."
        if exc.status_code == 409:
            return False, str(exc)
        raise
    role_label = "Admin" if target.get("role") == ROLE_ADMIN else "Operator"
    return True, f'{role_label} "{username}" removed.'
