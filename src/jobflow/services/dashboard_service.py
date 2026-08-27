from __future__ import annotations

from sqlalchemy.orm import Session

from jobflow.api.schemas import DashboardStats
from jobflow.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._repo = DashboardRepository(db)

    def get_stats(self) -> DashboardStats:
        return DashboardStats(**self._repo.get_stats())
