"""BFF FastAPI auth dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from kb_identity.application.authenticate import Authenticate, require_roles
from kb_identity.application.ports import AuthenticationError, AuthorizationError
from kb_identity.domain.principal import Principal, Role


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def get_authenticate(request: Request) -> Authenticate:
    auth = getattr(request.app.state, "authenticate", None)
    if auth is None:
        raise RuntimeError("Authenticate use case missing on app.state.authenticate")
    return auth  # type: ignore[no-any-return]


def require_principal(
    request: Request,
    auth: Annotated[Authenticate, Depends(get_authenticate)],
) -> Principal:
    try:
        return auth.execute(_extract_bearer(request))
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles_dep(*roles: Role) -> Callable[..., Principal]:
    def _dep(principal: Annotated[Principal, Depends(require_principal)]) -> Principal:
        try:
            require_roles(principal, *roles)
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return principal

    return _dep
