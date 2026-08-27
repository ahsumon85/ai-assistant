from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobflow.api.schemas import IntegrationStatus
from jobflow.auth.dependencies import get_current_user
from jobflow.auth.security import create_access_token
from jobflow.config import get_settings
from jobflow.db import get_db
from jobflow.db.models import OAuthToken, User
from jobflow.integrations.email_oauth import (
    GmailService,
    OutlookService,
    normalize_greenhouse_payload,
    normalize_lever_payload,
    verify_greenhouse_signature,
    verify_lever_signature,
)
from jobflow.ingestion.collector import JobCollector
from jobflow.services.bootstrap import create_background_task
from jobflow.workers.tasks import enqueue_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationStatus)
def integration_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IntegrationStatus:
    gmail = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user.id, OAuthToken.provider == "gmail"))
    outlook = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user.id, OAuthToken.provider == "outlook"))
    return IntegrationStatus(
        gmail_connected=bool(gmail and gmail.refresh_token),
        outlook_connected=bool(outlook and outlook.access_token),
        gmail_email=gmail.email_address if gmail else None,
        outlook_email=outlook.email_address if outlook else None,
    )


@router.get("/gmail/connect")
def gmail_connect(user: User = Depends(get_current_user)) -> dict[str, str]:
    settings = get_settings()
    if not settings.gmail_client_id:
        raise HTTPException(status_code=400, detail="Gmail client ID not configured")
    state = create_access_token(user.id)
    url = GmailService().get_auth_url(state)
    return {"auth_url": url}


@router.get("/gmail/callback")
def gmail_callback(code: str, state: str, db: Session = Depends(get_db)):
    from jobflow.auth.security import decode_access_token

    user_id = decode_access_token(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state")
    tokens = GmailService().exchange_code(code)
    existing = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == "gmail"))
    if existing:
        existing.access_token = tokens.get("access_token")
        existing.refresh_token = tokens.get("refresh_token") or existing.refresh_token
        existing.token_expiry = None
    else:
        db.add(
            OAuthToken(
                id=str(uuid4()),
                user_id=user_id,
                provider="gmail",
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
            )
        )
    db.commit()
    settings = get_settings()
    return RedirectResponse(f"{settings.frontend_url}/settings?gmail=connected")


@router.get("/outlook/connect")
def outlook_connect(user: User = Depends(get_current_user)) -> dict[str, str]:
    settings = get_settings()
    if not settings.outlook_client_id:
        raise HTTPException(status_code=400, detail="Outlook client ID not configured")
    state = create_access_token(user.id)
    url = OutlookService().get_auth_url(state)
    return {"auth_url": url}


@router.get("/outlook/callback")
def outlook_callback(code: str, state: str, db: Session = Depends(get_db)):
    from jobflow.auth.security import decode_access_token

    user_id = decode_access_token(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state")
    tokens = OutlookService().exchange_code(code)
    existing = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == "outlook"))
    if existing:
        existing.access_token = tokens.get("access_token")
        existing.refresh_token = tokens.get("refresh_token") or existing.refresh_token
    else:
        db.add(
            OAuthToken(
                id=str(uuid4()),
                user_id=user_id,
                provider="outlook",
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
            )
        )
    db.commit()
    settings = get_settings()
    return RedirectResponse(f"{settings.frontend_url}/settings?outlook=connected")


@router.post("/webhooks/greenhouse")
async def greenhouse_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_greenhouse_signature: str | None = Header(default=None),
    async_mode: bool = Query(default=True),
):
    body = await request.body()
    if not verify_greenhouse_signature(body, x_greenhouse_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    import json
    payload = json.loads(body)
    normalized = normalize_greenhouse_payload(payload)
    if not normalized:
        return {"status": "ignored"}
    if async_mode:
        task = create_background_task(db, task_type="ingest_webhook", payload={"payload": normalized})
        db.commit()
        await enqueue_task("ingest_webhook", task.id, payload=normalized)
        return {"status": "queued", "task_id": task.id}
    return JobCollector(db).collect_webhook(normalized)


@router.post("/webhooks/lever")
async def lever_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_lever_signature: str | None = Header(default=None),
    async_mode: bool = Query(default=True),
):
    body = await request.body()
    if not verify_lever_signature(body, x_lever_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    import json
    payload = json.loads(body)
    normalized = normalize_lever_payload(payload)
    if not normalized:
        return {"status": "ignored"}
    if async_mode:
        task = create_background_task(db, task_type="ingest_webhook", payload={"payload": normalized})
        db.commit()
        await enqueue_task("ingest_webhook", task.id, payload=normalized)
        return {"status": "queued", "task_id": task.id}
    return JobCollector(db).collect_webhook(normalized)
