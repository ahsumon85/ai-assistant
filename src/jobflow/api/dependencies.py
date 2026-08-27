"""FastAPI dependency providers for services."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from jobflow.db import get_db
from jobflow.services.application_service import ApplicationService
from jobflow.services.auth_service import AuthService
from jobflow.services.candidate_service import CandidateService
from jobflow.services.dashboard_service import DashboardService
from jobflow.services.ingestion_service import IngestionService
from jobflow.services.integration_service import IntegrationService
from jobflow.services.job_service import JobService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_candidate_service(db: Session = Depends(get_db)) -> CandidateService:
    return CandidateService(db)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(db)


def get_application_service(db: Session = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionService:
    return IngestionService(db)


def get_integration_service(db: Session = Depends(get_db)) -> IntegrationService:
    return IntegrationService(db)
