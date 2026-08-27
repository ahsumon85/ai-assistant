from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header

from jobflow.api.dependencies import get_ingestion_service
from jobflow.api.schemas import EmailSyncRequest
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/webhook")
async def ingest_webhook(
    payload: dict[str, Any] | list[dict[str, Any]],
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    return service.collect_webhook(payload, x_api_key)


@router.get("/email/status")
def email_ingest_status(
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    return service.email_status()


@router.post("/email/sync")
def sync_email_jobs(
    payload: EmailSyncRequest,
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    return service.sync_email(payload)
