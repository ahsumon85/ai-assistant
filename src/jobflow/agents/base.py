from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jobflow.db.models import AgentRun, AgentRunStatus
from jobflow.services.llm import LLMClient


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, db: Session, llm: LLMClient | None = None):
        self.db = db
        self.llm = llm or LLMClient()

    def run(self, *, job_id: str | None = None, application_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        run = AgentRun(
            id=str(uuid4()),
            job_id=job_id,
            application_id=application_id,
            agent_name=self.name,
            status=AgentRunStatus.RUNNING,
            input_payload=kwargs,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()

        try:
            output = self.execute(job_id=job_id, application_id=application_id, **kwargs)
            run.status = AgentRunStatus.SUCCEEDED
            run.output_payload = output
            run.finished_at = datetime.now(timezone.utc)
            self.db.flush()
            return output
        except Exception as exc:  # noqa: BLE001
            run.status = AgentRunStatus.FAILED
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            self.db.flush()
            raise

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError
