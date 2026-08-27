from __future__ import annotations

from sqlalchemy import func, select

from jobflow.db.models import (
    Application,
    ApplicationStatus,
    BackgroundTask,
    BackgroundTaskStatus,
    Job,
    JobStatus,
)
from jobflow.repositories.base import BaseRepository


class DashboardRepository(BaseRepository):
    def get_stats(self) -> dict[str, int]:
        total_jobs = self.db.scalar(select(func.count()).select_from(Job)) or 0
        new_jobs = self.db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.NEW)
        ) or 0
        matched = self.db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_([JobStatus.MATCHED, JobStatus.AWAITING_APPROVAL, JobStatus.PREPARING]))
        ) or 0
        rejected = self.db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.REJECTED)
        ) or 0
        awaiting = self.db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.status == ApplicationStatus.AWAITING_APPROVAL)
        ) or 0
        sent = self.db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.status == ApplicationStatus.SENT)
        ) or 0
        pending_tasks = self.db.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(
                BackgroundTask.status.in_([BackgroundTaskStatus.QUEUED, BackgroundTaskStatus.RUNNING])
            )
        ) or 0
        return {
            "total_jobs": total_jobs,
            "new_jobs": new_jobs,
            "matched_jobs": matched,
            "rejected_jobs": rejected,
            "awaiting_approval": awaiting,
            "sent_applications": sent,
            "pending_tasks": pending_tasks,
        }
