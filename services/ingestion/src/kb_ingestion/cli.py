"""CLI: ingest a company filing from SEC EDGAR."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from kb_domain import CIK

from kb_ingestion.application.use_cases.ingest_filing import IngestFilingCommand
from kb_ingestion.infrastructure.wiring import (
    build_compose_ingest,
    build_local_ingest,
    build_memory_ingest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kb-ingest",
        description="Ingest the latest EDGAR filing for a CIK (fetch → parse → chunk → embed).",
    )
    parser.add_argument(
        "--cik",
        required=True,
        help="SEC CIK (e.g. 320193 or 0000320193)",
    )
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT", ""),
        help="SEC-required User-Agent including contact email (or set SEC_USER_AGENT)",
    )
    parser.add_argument(
        "--backend",
        choices=("local", "memory", "compose"),
        default=os.environ.get("KB_DATA_PLANE", "local"),
        help="local=FS+sqlite; memory=ephemeral; compose=MinIO+Postgres+OpenSearch",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("INGEST_DATA_DIR", "data/ingestion")),
        help="Data directory for local backend (default: data/ingestion)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even if accession is already at cursor",
    )
    parser.add_argument(
        "--forms",
        default="10-K,10-Q,8-K",
        help="Comma-separated form types to accept (default: 10-K,10-Q,8-K)",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    user_agent = args.user_agent.strip()
    if not user_agent:
        print(
            "error: SEC User-Agent required. Pass --user-agent "
            "'YourApp name@example.com' or set SEC_USER_AGENT."
        )
        return 2

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print(
            "error: OPENAI_API_KEY is required for live embeddings. "
            "Set it in the environment or .env."
        )
        return 2

    forms = tuple(part.strip() for part in args.forms.split(",") if part.strip())
    runtime = None
    try:
        if args.backend == "local":
            runtime = build_local_ingest(user_agent=user_agent, data_dir=args.data_dir)
        elif args.backend == "compose":
            runtime = await build_compose_ingest(user_agent=user_agent)
        else:
            runtime = build_memory_ingest(user_agent=user_agent)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to wire backend {args.backend}: {exc}")
        return 2

    try:
        result = await runtime.use_case.execute(
            IngestFilingCommand(cik=CIK(args.cik), form_types=forms, force=args.force)
        )
    finally:
        await runtime.edgar.aclose()
        aclose = getattr(runtime.embedder, "aclose", None)
        if callable(aclose):
            await aclose()
        if runtime.postgres_store is not None:
            await runtime.postgres_store.aclose()

    if result.skipped:
        print(f"skipped accession={result.accession_no} (already ingested; use --force)")
        return 0

    dims = getattr(runtime.embedder, "dimensions", "?")
    print(
        "ingested "
        f"accession={result.accession_no} "
        f"chunks={result.chunk_count} "
        f"raw={result.s3_raw_path} "
        f"embedder={runtime.embedder_label} dims={dims} "
        f"backend={args.backend}"
    )
    if runtime.data_dir is not None:
        print(f"data_dir={runtime.data_dir.resolve()}")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
