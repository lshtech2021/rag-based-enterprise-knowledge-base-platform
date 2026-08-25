"""Build the TokenValidatorPort for the configured auth mode."""

from __future__ import annotations

from kb_identity.application.ports import TokenValidatorPort
from kb_identity.infrastructure.dev_bypass import DevBypassAuthenticator
from kb_identity.infrastructure.hmac_jwt import HmacJwtAuthenticator


def build_authenticator(auth_mode: str, *, jwt_secret: str = "") -> TokenValidatorPort:
    mode = auth_mode.strip().lower()
    if mode == "dev_bypass":
        return DevBypassAuthenticator()
    if mode == "oidc":
        return HmacJwtAuthenticator(jwt_secret)
    raise ValueError(f"Unsupported auth_mode: {auth_mode!r}")
