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
    assert "postgres_ok" not in body


class _FakePing:
    async def ping(self) -> bool:
        return True


class _FakeQueryRuntime:
    def __init__(self, postgres_store: object) -> None:
        self.postgres_store = postgres_store


class _FakeIngestRuntime:
    def __init__(self, postgres_store: object, search_index: object) -> None:
        self.postgres_store = postgres_store
        self.search_index = search_index


def test_healthz_reports_compose_readiness_without_live_network(tmp_path) -> None:
    """Compose plane exposes postgres/minio/opensearch pings via app.state,
    exercised here with fakes so the test never touches a live network."""
    settings = Settings(
        auth_mode="dev_bypass",
        jwt_secret="test",
        sec_user_agent="",
        openai_api_key="",
        ingest_data_dir=str(tmp_path / "ingestion"),
        kb_data_plane="compose",
    )
    app = create_app(settings)
    pg = _FakePing()
    # Pre-set everything the lifespan would otherwise try to build for
    # `compose` (which needs live Postgres/MinIO/OpenSearch) so this stays a
    # fast, offline unit test.
    app.state.answer_query = object()
    app.state.ingest_filing = object()
    app.state.generate_report = object()
    app.state.report_repository = object()
    app.state.query_runtime = _FakeQueryRuntime(pg)
    app.state.ingest_runtime = _FakeIngestRuntime(pg, _FakePing())
    app.state.object_store = _FakePing()

    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["data_plane"] == "compose"
    assert body["postgres_ok"] is True
    assert body["minio_ok"] is True
    assert body["opensearch_ok"] is True
