from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from jobflow.api.schemas import DashboardStats
from jobflow.auth.dependencies import get_current_user
from jobflow.db import get_db
from jobflow.db.models import Application, ApplicationStatus, BackgroundTask, BackgroundTaskStatus, Job, JobStatus, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardStats:
    total_jobs = db.scalar(select(func.count()).select_from(Job)) or 0
    new_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.status == JobStatus.NEW)) or 0
    matched = db.scalar(
        select(func.count()).select_from(Job).where(Job.status.in_([JobStatus.MATCHED, JobStatus.AWAITING_APPROVAL, JobStatus.PREPARING]))
    ) or 0
    rejected = db.scalar(select(func.count()).select_from(Job).where(Job.status == JobStatus.REJECTED)) or 0
    awaiting = db.scalar(
        select(func.count()).select_from(Application).where(Application.status == ApplicationStatus.AWAITING_APPROVAL)
    ) or 0
    sent = db.scalar(
        select(func.count()).select_from(Application).where(Application.status == ApplicationStatus.SENT)
    ) or 0
    pending_tasks = db.scalar(
        select(func.count()).select_from(BackgroundTask).where(
            BackgroundTask.status.in_([BackgroundTaskStatus.QUEUED, BackgroundTaskStatus.RUNNING])
        )
    ) or 0
    return DashboardStats(
        total_jobs=total_jobs,
        new_jobs=new_jobs,
        matched_jobs=matched,
        rejected_jobs=rejected,
        awaiting_approval=awaiting,
        sent_applications=sent,
        pending_tasks=pending_tasks,
    )
