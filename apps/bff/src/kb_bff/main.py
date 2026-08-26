from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kb_identity import Authenticate, build_authenticator
from kb_ingestion.infrastructure.object_store.local_fs import LocalFilesystemObjectStore
from kb_ingestion.infrastructure.object_store.minio_store import MinioObjectStore
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_ingestion.infrastructure.wiring import build_compose_ingest, build_local_ingest
from kb_observability import InMemoryLlmObserver, setup_inmemory_tracer
from kb_query.infrastructure.wiring import (
    build_compose_answer_query,
    build_local_answer_query,
)
from kb_report.application.use_cases.generate_report import GenerateReport
from kb_report.infrastructure.answer_query_adapter import AnswerQuerySectionAdapter
from kb_report.infrastructure.in_memory_report_store import InMemoryReportRepository
from kb_report.infrastructure.postgres_report_store import PostgresReportRepository

from kb_bff.identity_router import router as identity_router
from kb_bff.ingest_router import router as ingest_router
from kb_bff.logging_utils import configure_logging, get_logger, log_event
from kb_bff.query_router import router as query_router
from kb_bff.report_router import router as report_router
from kb_bff.settings import Settings, get_settings
from kb_bff.tracing import TracingMiddleware

_log = get_logger("kb_bff.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    data_dir = Path(settings.ingest_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    ingest_runtime = None
    query_runtime = None
    report_store: PostgresReportRepository | None = None
    plane = (settings.kb_data_plane or "local").strip().lower()
    app.state.data_plane = plane
    log_event(_log, logging.INFO, "lifespan.start", data_plane=plane)

    # Tests may inject fakes before the client starts; do not overwrite them.
    if getattr(app.state, "filing_repository", None) is None and plane != "compose":
        app.state.filing_repository = SqliteKnowledgeStore(data_dir / "ingestion.sqlite3")
    if getattr(app.state, "object_store", None) is None and plane != "compose":
        app.state.object_store = LocalFilesystemObjectStore(data_dir / "raw")

    has_keys = bool(settings.sec_user_agent.strip() and settings.openai_api_key.strip())
    openai_api_key = settings.openai_api_key.strip() or None
    openai_base_url = settings.openai_base_url.strip() or None
    openai_embedding_model = settings.openai_embedding_model.strip() or None
    openai_chat_model = settings.openai_chat_model.strip() or None
    embedding_dimensions = settings.embedding_dimensions
    embedding_batch_size = (
        settings.embedding_batch_size if settings.embedding_batch_size > 0 else None
    )
    if getattr(app.state, "ingest_filing", None) is None and has_keys:
        try:
            if plane == "compose":
                ingest_runtime = await build_compose_ingest(
                    user_agent=settings.sec_user_agent.strip(),
                    database_url=settings.database_url,
                    minio_endpoint=settings.minio_endpoint,
                    minio_access_key=settings.minio_access_key,
                    minio_secret_key=settings.minio_secret_key,
                    minio_bucket=settings.minio_bucket,
                    opensearch_url=settings.opensearch_url,
                    opensearch_username=settings.opensearch_username,
                    opensearch_password=settings.opensearch_password,
                    embedding_dimensions=embedding_dimensions,
                    embedding_batch_size=embedding_batch_size,
                    openai_api_key=openai_api_key,
                    openai_base_url=openai_base_url,
                    openai_embedding_model=openai_embedding_model,
                )
            else:
                ingest_runtime = build_local_ingest(
                    user_agent=settings.sec_user_agent.strip(),
                    data_dir=data_dir,
                    embedding_dimensions=embedding_dimensions,
                    embedding_batch_size=embedding_batch_size,
                    openai_api_key=openai_api_key,
                    openai_base_url=openai_base_url,
                    openai_embedding_model=openai_embedding_model,
                )
            app.state.ingest_filing = ingest_runtime.use_case
            app.state.filing_repository = ingest_runtime.filings
            app.state.object_store = ingest_runtime.object_store
            app.state.ingest_runtime = ingest_runtime
            log_event(
                _log,
                logging.INFO,
                "lifespan.ingest_wired",
                data_plane=plane,
                embedder=ingest_runtime.embedder_label,
            )
        except Exception as exc:
            log_event(
                _log,
                logging.ERROR,
                "lifespan.ingest_failed",
                data_plane=plane,
                error=type(exc).__name__,
            )
            raise

    if getattr(app.state, "answer_query", None) is None and settings.openai_api_key.strip():
        try:
            if plane == "compose":
                query_runtime = await build_compose_answer_query(
                    database_url=settings.database_url,
                    opensearch_url=settings.opensearch_url,
                    opensearch_username=settings.opensearch_username,
                    opensearch_password=settings.opensearch_password,
                    openai_api_key=settings.openai_api_key.strip(),
                    openai_base_url=openai_base_url,
                    embedding_model=openai_embedding_model,
                    embedding_dimensions=embedding_dimensions,
                    chat_model=openai_chat_model,
                )
            else:
                query_runtime = await build_local_answer_query(
                    data_dir=data_dir,
                    openai_api_key=settings.openai_api_key.strip(),
                    openai_base_url=openai_base_url,
                    embedding_model=openai_embedding_model,
                    embedding_dimensions=embedding_dimensions,
                    chat_model=openai_chat_model,
                )
            app.state.answer_query = query_runtime.use_case
            app.state.query_runtime = query_runtime
            log_event(
                _log,
                logging.INFO,
                "lifespan.query_wired",
                data_plane=plane,
                corpus_chunks=query_runtime.corpus_size,
            )
        except Exception as exc:
            log_event(
                _log,
                logging.ERROR,
                "lifespan.query_failed",
                data_plane=plane,
                error=type(exc).__name__,
            )
            raise

    if (
        getattr(app.state, "generate_report", None) is None
        and getattr(app.state, "answer_query", None) is not None
    ):
        try:
            if getattr(app.state, "report_repository", None) is None:
                if plane == "compose":
                    report_object_store = MinioObjectStore(
                        endpoint=settings.minio_endpoint,
                        access_key=settings.minio_access_key,
                        secret_key=settings.minio_secret_key,
                        bucket=settings.minio_bucket,
                    )
                    report_store = await PostgresReportRepository.connect(
                        settings.database_url,
                        object_store=report_object_store,
                    )
                    app.state.report_repository = report_store
                else:
                    app.state.report_repository = InMemoryReportRepository()
            app.state.generate_report = GenerateReport(
                answers=AnswerQuerySectionAdapter(app.state.answer_query),
                reports=app.state.report_repository,
            )
            log_event(_log, logging.INFO, "lifespan.report_wired", data_plane=plane)
        except Exception as exc:
            log_event(
                _log,
                logging.ERROR,
                "lifespan.report_failed",
                data_plane=plane,
                error=type(exc).__name__,
            )
            raise

    corpus_chunks = 0
    if query_runtime is not None:
        corpus_chunks = query_runtime.corpus_size
    else:
        filing_repo = getattr(app.state, "filing_repository", None)
        count_fn = getattr(filing_repo, "corpus_chunk_count", None)
        if callable(count_fn):
            corpus_chunks = await count_fn()
    app.state.corpus_chunks = corpus_chunks
    log_event(
        _log,
        logging.INFO,
        "lifespan.ready",
        data_plane=plane,
        ingest_configured=getattr(app.state, "ingest_filing", None) is not None,
        query_configured=getattr(app.state, "answer_query", None) is not None,
        report_configured=getattr(app.state, "generate_report", None) is not None,
        corpus_chunks=corpus_chunks,
    )

    try:
        yield
    finally:
        log_event(_log, logging.INFO, "lifespan.shutdown", data_plane=plane)
        if ingest_runtime is not None:
            await ingest_runtime.edgar.aclose()
            aclose = getattr(ingest_runtime.embedder, "aclose", None)
            if callable(aclose):
                await aclose()
            if ingest_runtime.postgres_store is not None:
                await ingest_runtime.postgres_store.aclose()
        if query_runtime is not None:
            await query_runtime.embedder.aclose()
            await query_runtime.llm.aclose()
            if query_runtime.postgres_store is not None:
                await query_runtime.postgres_store.aclose()
        if report_store is not None:
            await report_store.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)
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
    async def healthz() -> dict[str, object]:
        plane = getattr(app.state, "data_plane", cfg.kb_data_plane)
        body: dict[str, object] = {
            "status": "ok",
            "auth_mode": cfg.auth_mode,
            "tracing": "otel-inmemory",
            "data_plane": plane,
            "ingest_configured": getattr(app.state, "ingest_filing", None) is not None,
            "query_configured": getattr(app.state, "answer_query", None) is not None,
            "report_configured": getattr(app.state, "generate_report", None) is not None,
            "corpus_chunks": int(getattr(app.state, "corpus_chunks", 0) or 0),
        }
        if plane == "compose":
            body.update(await _compose_readiness(app))
        log_event(
            _log,
            logging.DEBUG,
            "healthz",
            data_plane=plane,
            ingest_configured=body["ingest_configured"],
            query_configured=body["query_configured"],
            report_configured=body["report_configured"],
            corpus_chunks=body["corpus_chunks"],
            postgres_ok=body.get("postgres_ok"),
            minio_ok=body.get("minio_ok"),
            opensearch_ok=body.get("opensearch_ok"),
        )
        return body

    return app


async def _compose_readiness(app: FastAPI) -> dict[str, object]:
    """Best-effort Postgres/MinIO/OpenSearch pings for the compose data plane."""
    query_runtime = getattr(app.state, "query_runtime", None)
    ingest_runtime = getattr(app.state, "ingest_runtime", None)

    postgres_store = None
    if query_runtime is not None:
        postgres_store = query_runtime.postgres_store
    if postgres_store is None and ingest_runtime is not None:
        postgres_store = ingest_runtime.postgres_store
    postgres_ok = await postgres_store.ping() if postgres_store is not None else False

    object_store = getattr(app.state, "object_store", None)
    minio_ping = getattr(object_store, "ping", None)
    minio_ok = await minio_ping() if callable(minio_ping) else False

    search_index = ingest_runtime.search_index if ingest_runtime is not None else None
    opensearch_ping = getattr(search_index, "ping", None)
    opensearch_ok = await opensearch_ping() if callable(opensearch_ping) else False

    return {
        "postgres_ok": postgres_ok,
        "minio_ok": minio_ok,
        "opensearch_ok": opensearch_ok,
    }


app = create_app()
