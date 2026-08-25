"""Authenticate requests and enforce RBAC."""

from __future__ import annotations

from kb_identity.application.ports import (
    AuthorizationError,
    TokenValidatorPort,
)
from kb_identity.domain.principal import Principal, Role


class Authenticate:
    def __init__(self, validator: TokenValidatorPort) -> None:
        self._validator = validator

    def execute(self, bearer_token: str | None) -> Principal:
        return self._validator.authenticate(bearer_token)


def require_roles(principal: Principal, *roles: Role) -> None:
    needed = set(roles)
    if not principal.has_any_role(needed):
        raise AuthorizationError(
            f"Principal {principal.user_id} missing roles {[r.value for r in roles]}"
        )
