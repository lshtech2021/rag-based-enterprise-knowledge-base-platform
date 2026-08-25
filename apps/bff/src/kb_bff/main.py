from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kb_identity import Authenticate, build_authenticator
from kb_observability import InMemoryLlmObserver, setup_inmemory_tracer

from kb_bff.identity_router import router as identity_router
from kb_bff.query_router import router as query_router
from kb_bff.report_router import router as report_router
from kb_bff.settings import Settings, get_settings
from kb_bff.tracing import TracingMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="Knowledge Base BFF", version="0.1.0")
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

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "auth_mode": cfg.auth_mode,
            "tracing": "otel-inmemory",
        }

    return app


app = create_app()
