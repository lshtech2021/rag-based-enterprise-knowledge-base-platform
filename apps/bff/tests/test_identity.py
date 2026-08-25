from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_bff.query_router import get_answer_query
from kb_bff.settings import Settings
from kb_identity.infrastructure.hmac_jwt import HmacJwtAuthenticator

SECRET = "test-secret-at-least-32-bytes-long!!"


def test_me_dev_bypass() -> None:
    client = TestClient(create_app(Settings(auth_mode="dev_bypass")))
    response = client.get("/v1/me")
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "dev-user"
    assert "analyst" in body["roles"]
    assert body["auth_mode"] == "dev_bypass"


def test_me_oidc_requires_token() -> None:
    client = TestClient(create_app(Settings(auth_mode="oidc", jwt_secret=SECRET)))
    assert client.get("/v1/me").status_code == 401


def test_me_oidc_with_valid_token() -> None:
    client = TestClient(create_app(Settings(auth_mode="oidc", jwt_secret=SECRET)))
    token = HmacJwtAuthenticator(SECRET).issue_token(user_id="alice", roles=["analyst"])
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "alice"


def test_query_forbidden_without_analyst_role() -> None:
    app = create_app(Settings(auth_mode="oidc", jwt_secret=SECRET))
    app.dependency_overrides[get_answer_query] = lambda: object()
    client = TestClient(app)
    token = HmacJwtAuthenticator(SECRET).issue_token(user_id="ops", roles=["operator"])
    response = client.post(
        "/v1/query",
        json={"question": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
