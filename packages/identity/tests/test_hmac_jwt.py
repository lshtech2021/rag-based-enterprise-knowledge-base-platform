import pytest
from kb_identity.application.ports import AuthenticationError
from kb_identity.domain.principal import Role
from kb_identity.infrastructure.hmac_jwt import HmacJwtAuthenticator

SECRET = "test-secret-at-least-32-bytes-long!!"


def test_hmac_jwt_roundtrip() -> None:
    auth = HmacJwtAuthenticator(SECRET)
    token = auth.issue_token(user_id="u1", roles=[Role.ANALYST.value])
    principal = auth.authenticate(token)
    assert principal.user_id == "u1"
    assert Role.ANALYST in principal.roles
    assert principal.auth_mode == "oidc"


def test_hmac_jwt_rejects_missing_token() -> None:
    with pytest.raises(AuthenticationError):
        HmacJwtAuthenticator(SECRET).authenticate(None)


def test_hmac_jwt_rejects_bad_token() -> None:
    with pytest.raises(AuthenticationError):
        HmacJwtAuthenticator(SECRET).authenticate("not.a.jwt")
