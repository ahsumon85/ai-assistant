from __future__ import annotations

from fastapi import APIRouter, Depends

from jobflow.api.dependencies import get_ingestion_service
from jobflow.api.schemas import BackgroundTaskOut
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import BackgroundTask, User
from jobflow.services.ingestion_service import IngestionService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=BackgroundTaskOut)
def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> BackgroundTask:
    return service.get_task(task_id)
