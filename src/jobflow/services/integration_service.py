from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jobflow.api.schemas import IntegrationStatus
from jobflow.auth.security import create_access_token, decode_access_token
from jobflow.config import get_settings
from jobflow.db.models import OAuthToken, User
from jobflow.exceptions import UnauthorizedError, ValidationError
from jobflow.ingestion.collector import JobCollector
from jobflow.integrations.email_oauth import (
    GmailService,
    OutlookService,
    normalize_greenhouse_payload,
    normalize_lever_payload,
    verify_greenhouse_signature,
    verify_lever_signature,
)
from jobflow.repositories.oauth_token_repository import OAuthTokenRepository
from jobflow.services.bootstrap import create_background_task
from jobflow.workers.tasks import enqueue_task, redis_available

logger = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, db: Session) -> None:
        self._repo = OAuthTokenRepository(db)
        self._db = db

    def get_status(self, user: User) -> IntegrationStatus:
        gmail = self._repo.get_by_user_and_provider(user.id, "gmail")
        outlook = self._repo.get_by_user_and_provider(user.id, "outlook")
        return IntegrationStatus(
            gmail_connected=bool(gmail and gmail.refresh_token),
            outlook_connected=bool(outlook and outlook.access_token),
            gmail_email=gmail.email_address if gmail else None,
            outlook_email=outlook.email_address if outlook else None,
        )

    def gmail_connect_url(self, user: User) -> str:
        settings = get_settings()
        if not settings.gmail_client_id:
            raise ValidationError("Gmail client ID not configured")
        state = create_access_token(user.id)
        return GmailService().get_auth_url(state)

    def gmail_callback(self, code: str, state: str) -> str:
        user_id = decode_access_token(state)
        if not user_id:
            raise ValidationError("Invalid state")
        tokens = GmailService().exchange_code(code)
        existing = self._repo.get_by_user_and_provider(user_id, "gmail")
        token = OAuthToken(
            id=str(uuid4()),
            user_id=user_id,
            provider="gmail",
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
        )
        self._repo.upsert(token, existing)
        return f"{get_settings().frontend_url}/settings?gmail=connected"

    def outlook_connect_url(self, user: User) -> str:
        settings = get_settings()
        if not settings.outlook_client_id:
            raise ValidationError("Outlook client ID not configured")
        state = create_access_token(user.id)
        return OutlookService().get_auth_url(state)

    def outlook_callback(self, code: str, state: str) -> str:
        user_id = decode_access_token(state)
        if not user_id:
            raise ValidationError("Invalid state")
        tokens = OutlookService().exchange_code(code)
        existing = self._repo.get_by_user_and_provider(user_id, "outlook")
        token = OAuthToken(
            id=str(uuid4()),
            user_id=user_id,
            provider="outlook",
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
        )
        self._repo.upsert(token, existing)
        return f"{get_settings().frontend_url}/settings?outlook=connected"

    async def greenhouse_webhook(
        self, body: bytes, signature: str | None, async_mode: bool
    ) -> dict[str, Any]:
        if not verify_greenhouse_signature(body, signature):
            raise UnauthorizedError("Invalid signature")
        payload = json.loads(body)
        normalized = normalize_greenhouse_payload(payload)
        if not normalized:
            return {"status": "ignored"}
        return await self._handle_webhook_payload(normalized, async_mode)

    async def lever_webhook(
        self, body: bytes, signature: str | None, async_mode: bool
    ) -> dict[str, Any]:
        if not verify_lever_signature(body, signature):
            raise UnauthorizedError("Invalid signature")
        payload = json.loads(body)
        normalized = normalize_lever_payload(payload)
        if not normalized:
            return {"status": "ignored"}
        return await self._handle_webhook_payload(normalized, async_mode)

    async def _handle_webhook_payload(
        self, normalized: dict[str, Any], async_mode: bool
    ) -> dict[str, Any]:
        if async_mode and await redis_available():
            task = create_background_task(
                self._db, task_type="ingest_webhook", payload={"payload": normalized}
            )
            self._db.commit()
            await enqueue_task("ingest_webhook", task.id, payload=normalized)
            return {"status": "queued", "task_id": task.id}
        if async_mode:
            logger.warning("Redis unavailable — running ingest_webhook synchronously")
        return JobCollector(self._db).collect_webhook(normalized)
