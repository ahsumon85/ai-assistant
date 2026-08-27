from __future__ import annotations

from jobflow.db.models import BackgroundTask
from jobflow.repositories.base import BaseRepository


class BackgroundTaskRepository(BaseRepository):
    def get_by_id(self, task_id: str) -> BackgroundTask | None:
        return self.db.get(BackgroundTask, task_id)
