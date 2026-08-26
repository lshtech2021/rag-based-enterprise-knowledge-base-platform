"""Current-user identity routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from kb_identity.domain.principal import Principal

from kb_bff.auth_deps import require_principal
from kb_bff.logging_utils import get_logger, log_event

_log = get_logger("kb_bff.identity")

router = APIRouter(prefix="/v1", tags=["identity"])


@router.get("/me")
def me(principal: Annotated[Principal, Depends(require_principal)]) -> dict[str, object]:
    log_event(
        _log,
        logging.INFO,
        "identity.me",
        user_id=principal.user_id,
        auth_mode=principal.auth_mode,
    )
    return {
        "user_id": principal.user_id,
        "roles": sorted(r.value for r in principal.roles),
        "auth_mode": principal.auth_mode,
    }
