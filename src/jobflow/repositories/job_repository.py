from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from jobflow.db.models import Job
from jobflow.repositories.base import BaseRepository


class JobRepository(BaseRepository):
    def list_jobs(self, status: str | None = None) -> list[Job]:
        stmt = select(Job).options(joinedload(Job.company)).order_by(Job.created_at.desc())
        if status:
            stmt = stmt.where(Job.status == status)
        return list(self.db.scalars(stmt).unique().all())

    def get_by_id(self, job_id: str) -> Job | None:
        return self.db.scalar(
            select(Job).options(joinedload(Job.company)).where(Job.id == job_id)
        )
