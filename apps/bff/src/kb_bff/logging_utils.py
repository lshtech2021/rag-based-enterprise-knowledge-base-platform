"""Structured key=value logging helpers for the BFF."""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def truncate(text: str, n: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= n:
        return cleaned
    return cleaned[: max(0, n - 3)] + "..."


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if any(ch.isspace() for ch in text) or "=" in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit `event=... key=value ...` without raising on logging failures."""
    try:
        parts = [f"event={event}"]
        for key, value in fields.items():
            parts.append(f"{key}={_format_value(value)}")
        logger.log(level, " ".join(parts))
    except Exception:  # noqa: BLE001 — logging must never break requests
        pass


def configure_logging(level_name: str = "INFO") -> None:
    """Configure root logging once (safe under uvicorn / TestClient)."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(_parse_level(level_name))
        return
    logging.basicConfig(
        level=_parse_level(level_name),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _parse_level(level_name: str) -> int:
    return getattr(logging, level_name.strip().upper(), logging.INFO)
