"""Access / route logging coverage."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_bff.settings import Settings


def test_http_request_end_logged_for_me(caplog) -> None:
    settings = Settings(
        auth_mode="dev_bypass",
        jwt_secret="test",
        sec_user_agent="",
        openai_api_key="",
        kb_data_plane="local",
        log_level="INFO",
    )
    app = create_app(settings)
    with caplog.at_level(logging.INFO, logger="kb_bff.http"):
        with TestClient(app) as client:
            response = client.get("/v1/me")
    assert response.status_code == 200
    messages = [r.getMessage() for r in caplog.records if r.name == "kb_bff.http"]
    assert any("event=http.request.start" in m and "path=/v1/me" in m for m in messages)
    assert any("event=http.request.end" in m and "path=/v1/me" in m for m in messages)


def test_identity_me_business_log(caplog) -> None:
    settings = Settings(
        auth_mode="dev_bypass",
        jwt_secret="test",
        sec_user_agent="",
        openai_api_key="",
        kb_data_plane="local",
        log_level="INFO",
    )
    app = create_app(settings)
    with caplog.at_level(logging.INFO, logger="kb_bff.identity"):
        with TestClient(app) as client:
            response = client.get("/v1/me")
    assert response.status_code == 200
    messages = [r.getMessage() for r in caplog.records if r.name == "kb_bff.identity"]
    assert any("event=identity.me" in m and "user_id=" in m for m in messages)


def test_healthz_access_log_is_debug(caplog) -> None:
    settings = Settings(
        auth_mode="dev_bypass",
        jwt_secret="test",
        sec_user_agent="",
        openai_api_key="",
        kb_data_plane="local",
        log_level="INFO",
    )
    app = create_app(settings)
    with caplog.at_level(logging.INFO, logger="kb_bff.http"):
        with TestClient(app) as client:
            assert client.get("/healthz").status_code == 200
    info_http = [
        r.getMessage()
        for r in caplog.records
        if r.name == "kb_bff.http" and r.levelno >= logging.INFO
    ]
    assert not any("path=/healthz" in m for m in info_http)
