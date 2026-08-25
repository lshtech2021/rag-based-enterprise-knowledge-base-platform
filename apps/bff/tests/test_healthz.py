from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_bff.settings import Settings


def test_healthz_defaults_to_dev_bypass() -> None:
    client = TestClient(create_app(Settings(auth_mode="dev_bypass")))
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["auth_mode"] == "dev_bypass"
    assert body["tracing"] == "otel-inmemory"


def test_healthz_reflects_configured_auth_mode() -> None:
    client = TestClient(create_app(Settings(auth_mode="oidc")))
    response = client.get("/healthz")
    assert response.json()["auth_mode"] == "oidc"
