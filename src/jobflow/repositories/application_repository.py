from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from jobflow.db.models import Application, Job
from jobflow.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository):
    def list_applications(self, status: str | None = None) -> list[Application]:
        stmt = (
            select(Application)
            .options(joinedload(Application.job).joinedload(Job.company))
            .order_by(Application.created_at.desc())
        )
        if status:
            stmt = stmt.where(Application.status == status)
        return list(self.db.scalars(stmt).unique().all())

    def get_by_id(self, application_id: str) -> Application | None:
        return self.db.scalar(
            select(Application)
            .options(joinedload(Application.job).joinedload(Job.company))
            .where(Application.id == application_id)
        )
