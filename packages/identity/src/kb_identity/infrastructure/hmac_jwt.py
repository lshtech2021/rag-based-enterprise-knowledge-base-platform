"""HMAC JWT validator — local stand-in for OIDC access tokens."""

from __future__ import annotations

from typing import Any

import jwt
from kb_identity.application.ports import AuthenticationError
from kb_identity.domain.principal import Principal, Role


class HmacJwtAuthenticator:
    def __init__(self, secret: str, *, audience: str = "kb-api", issuer: str = "kb-local") -> None:
        if not secret:
            raise ValueError("JWT secret must not be empty in oidc mode")
        self._secret = secret
        self._audience = audience
        self._issuer = issuer

    def authenticate(self, bearer_token: str | None) -> Principal:
        if not bearer_token:
            raise AuthenticationError("Missing bearer token")
        try:
            payload: dict[str, Any] = jwt.decode(
                bearer_token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid bearer token") from exc

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise AuthenticationError("Token missing sub")

        raw_roles = payload.get("roles", [])
        if not isinstance(raw_roles, list):
            raise AuthenticationError("Token roles must be a list")
        roles: set[Role] = set()
        for item in raw_roles:
            if not isinstance(item, str):
                continue
            try:
                roles.add(Role(item))
            except ValueError:
                continue
        return Principal(user_id=sub, roles=frozenset(roles), auth_mode="oidc")

    def issue_token(self, *, user_id: str, roles: list[str], expires_seconds: int = 3600) -> str:
        """Helper for tests / local scripts — not for production IdP."""
        import time

        now = int(time.time())
        payload = {
            "sub": user_id,
            "roles": roles,
            "aud": self._audience,
            "iss": self._issuer,
            "iat": now,
            "exp": now + expires_seconds,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")
