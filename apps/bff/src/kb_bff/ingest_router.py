"""BFF ingestion routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from kb_application_ports import ObjectStorePort
from kb_domain import CIK
from kb_identity.domain.principal import Principal, Role
from kb_ingestion.application.ports import FilingRepository
from kb_ingestion.application.use_cases.ingest_filing import (
    IngestFiling,
    IngestFilingCommand,
)
from kb_ingestion.infrastructure.raw_download import (
    RawFilingNotFoundError,
    load_raw_filing,
)
from pydantic import BaseModel, Field

from kb_bff.auth_deps import require_roles_dep


class IngestRequest(BaseModel):
    cik: str = Field(min_length=1, max_length=20)
    form_types: list[str] = Field(default_factory=lambda: ["10-K", "10-Q", "8-K"])
    force: bool = False


def get_ingest_filing(request: Request) -> IngestFiling:
    use_case = getattr(request.app.state, "ingest_filing", None)
    if use_case is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion is not configured (need SEC_USER_AGENT and OPENAI_API_KEY)",
        )
    return use_case  # type: ignore[no-any-return]


def get_filing_repository(request: Request) -> FilingRepository:
    repo = getattr(request.app.state, "filing_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Filing repository is not configured",
        )
    return repo  # type: ignore[no-any-return]


def get_object_store(request: Request) -> ObjectStorePort:
    store = getattr(request.app.state, "object_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object store is not configured",
        )
    return store  # type: ignore[no-any-return]


router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post("/ingest")
async def create_ingest(
    body: IngestRequest,
    use_case: Annotated[IngestFiling, Depends(get_ingest_filing)],
    _principal: Annotated[Principal, Depends(require_roles_dep(Role.OPERATOR))],
) -> dict[str, object]:
    forms = tuple(part.strip() for part in body.form_types if part.strip())
    if not forms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="form_types must include at least one form",
        )
    try:
        result = await use_case.execute(
            IngestFilingCommand(
                cik=CIK(body.cik),
                form_types=forms,
                force=body.force,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface upstream EDGAR/OpenAI failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ingest failed: {exc}",
        ) from exc

    accession = str(result.accession_no)
    return {
        "accession_no": accession,
        "skipped": result.skipped,
        "chunk_count": result.chunk_count,
        "s3_raw_path": result.s3_raw_path,
        "download_url": f"/v1/filings/{accession}/raw",
    }


@router.get("/filings/{accession_no}/raw")
async def download_filing_raw(
    accession_no: str,
    filings: Annotated[FilingRepository, Depends(get_filing_repository)],
    object_store: Annotated[ObjectStorePort, Depends(get_object_store)],
    _principal: Annotated[Principal, Depends(require_roles_dep(Role.OPERATOR))],
) -> Response:
    try:
        body, filename = await load_raw_filing(
            filings=filings,
            object_store=object_store,
            accession_no=accession_no,
        )
    except RawFilingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filing not found: {accession_no}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
