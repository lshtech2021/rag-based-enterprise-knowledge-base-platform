"""Dev auth bypass — no token required."""

from __future__ import annotations

from kb_identity.domain.principal import Principal, Role


class DevBypassAuthenticator:
    def __init__(
        self,
        *,
        user_id: str = "dev-user",
        roles: frozenset[Role] | None = None,
    ) -> None:
        self._user_id = user_id
        self._roles = roles or frozenset({Role.ANALYST, Role.OPERATOR, Role.ADMIN})

    def authenticate(self, bearer_token: str | None) -> Principal:
        return Principal(
            user_id=self._user_id,
            roles=self._roles,
            auth_mode="dev_bypass",
        )
