from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from jobflow.api.schemas import EmailSyncRequest, IntegrationStatus
from jobflow.config import get_settings
from jobflow.db.models import BackgroundTask, User
from jobflow.exceptions import NotFoundError, UnauthorizedError, ValidationError
from jobflow.ingestion.collector import JobCollector
from jobflow.ingestion.email_client import ImapJobEmailClient
from jobflow.ingestion.email_sync import sync_jobs_from_email, sync_linkedin_emails
from jobflow.repositories.background_task_repository import BackgroundTaskRepository


class IngestionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._tasks = BackgroundTaskRepository(db)

    def collect_webhook(
        self, payload: dict[str, Any] | list[dict[str, Any]], api_key: str | None
    ) -> dict[str, Any]:
        settings = get_settings()
        if settings.ingest_api_key and api_key != settings.ingest_api_key:
            raise UnauthorizedError("Invalid API key")
        return JobCollector(self._db).collect_webhook(payload)

    def email_status(self) -> dict[str, Any]:
        return ImapJobEmailClient().status()

    def sync_email(self, payload: EmailSyncRequest) -> dict[str, Any]:
        if payload.source == "linkedin" and not payload.unseen_only:
            result = sync_linkedin_emails(
                self._db,
                limit=payload.limit,
                folder=payload.folder,
                date_from=payload.date_from,
                date_to=payload.date_to,
            )
        else:
            result = sync_jobs_from_email(
                self._db,
                limit=payload.limit,
                unseen_only=payload.unseen_only,
                source_filter=payload.source,
                folder=payload.folder,
                mark_read=payload.mark_read,
                date_from=payload.date_from,
                date_to=payload.date_to,
            )
        if result.get("status") == "error":
            raise ValidationError(result)
        return result

    def get_task(self, task_id: str) -> BackgroundTask:
        task = self._tasks.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task not found")
        return task
