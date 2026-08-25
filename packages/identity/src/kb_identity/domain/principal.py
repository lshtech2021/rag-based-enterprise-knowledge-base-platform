"""Authenticated principal and roles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    roles: frozenset[Role]
    auth_mode: str

    def has_role(self, role: Role) -> bool:
        return role in self.roles or Role.ADMIN in self.roles

    def has_any_role(self, roles: set[Role]) -> bool:
        if Role.ADMIN in self.roles:
            return True
        return bool(self.roles & roles)
