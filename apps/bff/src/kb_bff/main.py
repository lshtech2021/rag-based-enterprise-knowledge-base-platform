from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kb_identity import Authenticate, build_authenticator
from kb_ingestion.infrastructure.object_store.local_fs import LocalFilesystemObjectStore
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_ingestion.infrastructure.wiring import build_local_ingest
from kb_observability import InMemoryLlmObserver, setup_inmemory_tracer

from kb_bff.identity_router import router as identity_router
from kb_bff.ingest_router import router as ingest_router
from kb_bff.query_router import router as query_router
from kb_bff.report_router import router as report_router
from kb_bff.settings import Settings, get_settings
from kb_bff.tracing import TracingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    data_dir = Path(settings.ingest_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    runtime = None

    # Tests may inject fakes before the client starts; do not overwrite them.
    if getattr(app.state, "filing_repository", None) is None:
        app.state.filing_repository = SqliteKnowledgeStore(data_dir / "ingestion.sqlite3")
    if getattr(app.state, "object_store", None) is None:
        app.state.object_store = LocalFilesystemObjectStore(data_dir / "raw")

    if (
        getattr(app.state, "ingest_filing", None) is None
        and settings.sec_user_agent.strip()
        and settings.openai_api_key.strip()
    ):
        runtime = build_local_ingest(
            user_agent=settings.sec_user_agent.strip(),
            data_dir=data_dir,
        )
        app.state.ingest_filing = runtime.use_case
        app.state.filing_repository = runtime.filings
        app.state.object_store = runtime.object_store
        app.state.ingest_runtime = runtime

    try:
        yield
    finally:
        if runtime is not None:
            await runtime.edgar.aclose()
            aclose = getattr(runtime.embedder, "aclose", None)
            if callable(aclose):
                await aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="Knowledge Base BFF", version="0.1.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.authenticate = Authenticate(
        build_authenticator(cfg.auth_mode, jwt_secret=cfg.jwt_secret)
    )
    tracer = setup_inmemory_tracer(service_name="kb-bff")
    observer = InMemoryLlmObserver()
    app.state.tracer = tracer
    app.state.llm_observer = observer
    app.add_middleware(TracingMiddleware, tracer=tracer)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(identity_router)
    app.include_router(query_router)
    app.include_router(report_router)
    app.include_router(ingest_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "auth_mode": cfg.auth_mode,
            "tracing": "otel-inmemory",
        }

    return app


app = create_app()
