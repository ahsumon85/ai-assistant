from jobflow.api.controllers.application_controller import router as application_router
from jobflow.api.controllers.auth_controller import router as auth_router
from jobflow.api.controllers.candidate_controller import router as candidate_router
from jobflow.api.controllers.dashboard_controller import router as dashboard_router
from jobflow.api.controllers.health_controller import router as health_router
from jobflow.api.controllers.ingestion_controller import router as ingestion_router
from jobflow.api.controllers.integration_controller import router as integration_router
from jobflow.api.controllers.job_controller import router as job_router
from jobflow.api.controllers.task_controller import router as task_router

__all__ = [
    "application_router",
    "auth_router",
    "candidate_router",
    "dashboard_router",
    "health_router",
    "ingestion_router",
    "integration_router",
    "job_router",
    "task_router",
]
