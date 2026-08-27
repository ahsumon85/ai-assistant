from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from jobflow.api.schemas import JobOut
from jobflow.agents.supervisor import SupervisorAgent
from jobflow.exceptions import NotFoundError
from jobflow.repositories.job_repository import JobRepository
from jobflow.services.bootstrap import create_background_task
from jobflow.services.mappers import job_to_out
from jobflow.workers.tasks import enqueue_task, redis_available

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, db: Session) -> None:
        self._repo = JobRepository(db)
        self._db = db

    def list_jobs(self, status: str | None = None) -> list[JobOut]:
        return [job_to_out(j) for j in self._repo.list_jobs(status)]

    def get_job(self, job_id: str) -> JobOut:
        job = self._repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job not found")
        return job_to_out(job)

    async def process_job(
        self,
        job_id: str,
        candidate_id: str,
        contact_id: str | None,
        user_id: str,
        async_mode: bool,
    ) -> dict[str, Any]:
        if async_mode and await redis_available():
            task = create_background_task(
                self._db,
                task_type="process_job",
                payload={"job_id": job_id, "candidate_id": candidate_id, "contact_id": contact_id},
                user_id=user_id,
            )
            self._db.commit()
            await enqueue_task(
                "process_job",
                task.id,
                job_id=job_id,
                candidate_id=candidate_id,
                contact_id=contact_id,
            )
            return {"status": "queued", "task_id": task.id}
        if async_mode:
            logger.warning("Redis unavailable — running process_job synchronously")
        try:
            return SupervisorAgent(self._db, user_id=user_id).process_job(job_id, candidate_id, contact_id)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
