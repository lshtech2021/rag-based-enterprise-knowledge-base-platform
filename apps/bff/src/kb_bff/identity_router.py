"""Current-user identity routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from kb_identity.domain.principal import Principal

from kb_bff.auth_deps import require_principal

router = APIRouter(prefix="/v1", tags=["identity"])


@router.get("/me")
def me(principal: Annotated[Principal, Depends(require_principal)]) -> dict[str, object]:
    return {
        "user_id": principal.user_id,
        "roles": sorted(r.value for r in principal.roles),
        "auth_mode": principal.auth_mode,
    }
