from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from jobflow.api.schemas import ApplicationOut
from jobflow.agents.supervisor import SupervisorAgent
from jobflow.db.models import Application
from jobflow.exceptions import NotFoundError
from jobflow.repositories.application_repository import ApplicationRepository
from jobflow.services.mappers import application_to_out


class ApplicationService:
    def __init__(self, db: Session) -> None:
        self._repo = ApplicationRepository(db)
        self._db = db

    def list_applications(self, status: str | None = None) -> list[ApplicationOut]:
        return [application_to_out(a) for a in self._repo.list_applications(status)]

    def get_approval_detail(self, application_id: str) -> dict[str, Any]:
        app = self._repo.get_by_id(application_id)
        if not app:
            raise NotFoundError("Application not found")
        return {
            "id": app.id,
            "status": app.status,
            "job_title": app.job.title if app.job else None,
            "company": app.job.company.name if app.job and app.job.company else None,
            "match_score": app.job.match_score if app.job else None,
            "match_reasons": app.job.match_reasons if app.job else None,
            "missing_skills": app.job.missing_skills if app.job else None,
            "email_to": app.email_to,
            "email_subject": app.email_subject,
            "email_body": app.email_body,
            "cover_letter": app.cover_letter,
            "tailored_resume": app.tailored_resume,
            "recruiter_notes": app.recruiter_notes,
        }

    def approve(self, application_id: str, user_id: str, notes: str | None) -> dict[str, Any]:
        try:
            return SupervisorAgent(self._db, user_id=user_id).approve_application(application_id, notes)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc

    def reject(self, application_id: str, user_id: str, notes: str | None) -> dict[str, Any]:
        try:
            return SupervisorAgent(self._db, user_id=user_id).reject_application(application_id, notes)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
