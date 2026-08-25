from kb_identity.application.authenticate import Authenticate, require_roles
from kb_identity.application.ports import AuthorizationError
from kb_identity.domain.principal import Principal, Role
from kb_identity.infrastructure.dev_bypass import DevBypassAuthenticator


def test_dev_bypass_returns_analyst_principal() -> None:
    principal = DevBypassAuthenticator().authenticate(None)
    assert principal.user_id == "dev-user"
    assert principal.auth_mode == "dev_bypass"
    assert principal.has_role(Role.ANALYST)


def test_require_roles_allows_admin_for_any() -> None:
    principal = Principal(
        user_id="a",
        roles=frozenset({Role.ADMIN}),
        auth_mode="oidc",
    )
    require_roles(principal, Role.ANALYST)


def test_require_roles_rejects_missing() -> None:
    principal = Principal(
        user_id="a",
        roles=frozenset({Role.OPERATOR}),
        auth_mode="oidc",
    )
    try:
        require_roles(principal, Role.ANALYST)
        raise AssertionError("expected AuthorizationError")
    except AuthorizationError:
        pass


def test_authenticate_use_case_delegates() -> None:
    auth = Authenticate(DevBypassAuthenticator())
    assert auth.execute(None).user_id == "dev-user"
