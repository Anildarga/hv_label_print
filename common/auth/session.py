from __future__ import annotations

from common.auth.user_store import ROLE_ADMIN, ROLE_OPERATOR


class Session:

    def __init__(self) -> None:
        self.username: str | None = None
        self.role: str | None = None
        self._password: str | None = None

    @property
    def is_admin(self) -> bool:
        
        return self.role in (ROLE_ADMIN, ROLE_OPERATOR)

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

    @property
    def excel_password(self) -> str:
        return self._password or "06082003"

    def login(self, username: str, password: str, role: str) -> None:
        self.username = username
        self._password = password
        self.role = role

    def logout(self) -> None:
        self.username = None
        self._password = None
        self.role = None