"""Identity application ports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kb_identity.domain.principal import Principal


class AuthenticationError(Exception):
    """Raised when credentials are missing or invalid."""


class AuthorizationError(Exception):
    """Raised when the principal lacks required roles."""


@runtime_checkable
class TokenValidatorPort(Protocol):
    def authenticate(self, bearer_token: str | None) -> Principal:
        """Validate credentials and return a Principal.

        `bearer_token` is the raw token without the 'Bearer ' prefix, or None.
        """
        ...
