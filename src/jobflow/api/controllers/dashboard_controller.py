from __future__ import annotations

from fastapi import APIRouter, Depends

from jobflow.api.dependencies import get_dashboard_service
from jobflow.api.schemas import DashboardStats
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(
    user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardStats:
    return service.get_stats()
