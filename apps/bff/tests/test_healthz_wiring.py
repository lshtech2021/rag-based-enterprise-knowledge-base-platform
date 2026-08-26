from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_bff.settings import Settings


def test_healthz_flags_when_unconfigured(tmp_path) -> None:
    settings = Settings(
        auth_mode="dev_bypass",
        jwt_secret="test",
        sec_user_agent="",
        openai_api_key="",
        ingest_data_dir=str(tmp_path / "ingestion"),
        kb_data_plane="local",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data_plane"] == "local"
    assert body["ingest_configured"] is False
    assert body["query_configured"] is False
    assert body["report_configured"] is False
    assert body["corpus_chunks"] == 0
