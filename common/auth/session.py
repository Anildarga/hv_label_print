from __future__ import annotations

from common.auth.user_store import ROLE_ADMIN, ROLE_OPERATOR
from common.api_client import set_bearer_token


class Session:

    def __init__(self) -> None:
        self.username: str | None = None
        self.role: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_main_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def role_label(self) -> str:
        if self.role == ROLE_ADMIN:
            return "Admin"
        if self.role == ROLE_OPERATOR:
            return "Operator"
        return "User"

    def login(self, username: str, password: str, role: str) -> None:
        self.username = username
        self.role = role

    def logout(self) -> None:
        self.username = None
        self.role = None
        set_bearer_token(None)