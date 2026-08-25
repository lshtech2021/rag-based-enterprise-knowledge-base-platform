from __future__ import annotations

from fastapi import FastAPI

from kb_bff.query_router import router as query_router
from kb_bff.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="Knowledge Base BFF", version="0.1.0")
    app.state.settings = cfg
    app.include_router(query_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "auth_mode": cfg.auth_mode,
        }

    return app


app = create_app()
