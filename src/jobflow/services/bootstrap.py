from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobflow.config import get_settings
from jobflow.db.models import BackgroundTask, BackgroundTaskStatus, Candidate, User
from jobflow.auth.security import hash_password

logger = logging.getLogger(__name__)


def ensure_default_admin(db: Session) -> None:
    settings = get_settings()
    existing = db.scalar(select(User).where(User.email == settings.default_admin_email))
    if existing:
        return
    admin = User(
        id=str(uuid4()),
        email=settings.default_admin_email,
        hashed_password=hash_password(settings.default_admin_password),
        full_name="Admin",
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    logger.info("Created default admin user: %s", settings.default_admin_email)


def ensure_default_candidate(db: Session) -> None:
    settings = get_settings()
    admin = db.scalar(select(User).where(User.email == settings.default_admin_email))
    if not admin:
        return
    existing = db.scalar(select(Candidate).where(Candidate.user_id == admin.id))
    if existing:
        return
    db.add(
        Candidate(
            id=str(uuid4()),
            user_id=admin.id,
            full_name=admin.full_name or "Admin",
            email=admin.email,
        )
    )
    db.commit()
    logger.info("Created default candidate profile for: %s", settings.default_admin_email)


def create_background_task(
    db: Session,
    *,
    task_type: str,
    payload: dict,
    user_id: str | None = None,
) -> BackgroundTask:
    task = BackgroundTask(
        id=str(uuid4()),
        user_id=user_id,
        task_type=task_type,
        status=BackgroundTaskStatus.QUEUED,
        payload=payload,
    )
    db.add(task)
    db.flush()
    return task


def mark_task_running(db: Session, task_id: str) -> BackgroundTask:
    task = db.get(BackgroundTask, task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    task.status = BackgroundTaskStatus.RUNNING
    task.started_at = datetime.now(timezone.utc)
    db.flush()
    return task


def mark_task_done(db: Session, task_id: str, result: dict) -> None:
    task = db.get(BackgroundTask, task_id)
    if not task:
        return
    task.status = BackgroundTaskStatus.SUCCEEDED
    task.result = result
    task.finished_at = datetime.now(timezone.utc)
    db.commit()


def mark_task_failed(db: Session, task_id: str, error: str) -> None:
    task = db.get(BackgroundTask, task_id)
    if not task:
        return
    task.status = BackgroundTaskStatus.FAILED
    task.error = error
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
