from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jobflow.agents.analysis import build_analysis_agents
from jobflow.agents.application import build_application_agents
from jobflow.config import get_settings
from jobflow.db.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Contact,
    Job,
    JobStatus,
)
from jobflow.email.provider import get_email_provider
from jobflow.integrations import get_email_provider_for_user
from jobflow.match.engine import MatchEngine
from jobflow.services.llm import LLMClient


class SupervisorAgent:
    """
    AI Orchestrator — coordinates analysis agents, match engine,
    application preparation, human approval, send, and follow-up.
    """

    name = "supervisor"

    def __init__(self, db: Session, llm: LLMClient | None = None, user_id: str | None = None):
        self.db = db
        self.llm = llm or LLMClient()
        self.user_id = user_id
        self.settings = get_settings()
        self.analysis_agents = build_analysis_agents(db, self.llm)
        self.app_agents = build_application_agents(db, self.llm)
        self.match_engine = MatchEngine(self.settings.match_threshold)
        self.email_provider = get_email_provider_for_user(db, user_id) if user_id else get_email_provider()

    def process_job(self, job_id: str, candidate_id: str, contact_id: str | None = None) -> dict[str, Any]:
        job = self.db.get(Job, job_id)
        candidate = self.db.get(Candidate, candidate_id)
        if not job or not candidate:
            raise ValueError("Job or candidate not found")

        candidate_payload = self._candidate_payload(candidate)
        contact_payload = self._contact_payload(contact_id)

        analysis = self.analysis_agents["job_analyzer"].run(job_id=job_id)
        fit = self.analysis_agents["job_fit"].run(job_id=job_id, candidate=candidate_payload)
        research = self.analysis_agents["company_researcher"].run(job_id=job_id)

        match = self.match_engine.score(analysis=analysis, fit=fit, research=research)
        job.match_score = match.score
        job.match_reasons = match.reasons
        job.missing_skills = match.missing_skills

        if not match.passed:
            job.status = JobStatus.REJECTED
            self.db.commit()
            return {
                "job_id": job_id,
                "decision": "reject",
                "match": match.to_dict(),
            }

        job.status = JobStatus.MATCHED
        application = Application(
            id=str(uuid4()),
            job_id=job.id,
            candidate_id=candidate.id,
            contact_id=contact_id,
            status=ApplicationStatus.DRAFT,
            artifacts={"match": match.to_dict(), "research": research},
        )
        self.db.add(application)
        self.db.flush()

        job.status = JobStatus.PREPARING
        self.app_agents["resume_agent"].run(
            job_id=job_id,
            application_id=application.id,
            candidate=candidate_payload,
        )
        self.app_agents["cover_letter_agent"].run(
            job_id=job_id,
            application_id=application.id,
            candidate=candidate_payload,
            research=research,
        )
        self.app_agents["recruiter_agent"].run(
            job_id=job_id,
            application_id=application.id,
            candidate=candidate_payload,
            research=research,
            contact=contact_payload,
        )
        email_draft = self.app_agents["email_agent"].run(application_id=application.id)

        application.status = ApplicationStatus.AWAITING_APPROVAL
        job.status = JobStatus.AWAITING_APPROVAL
        self.db.commit()

        return {
            "job_id": job_id,
            "decision": "prepare",
            "application_id": application.id,
            "match": match.to_dict(),
            "email_draft": email_draft,
            "requires_human_approval": True,
        }

    def approve_application(self, application_id: str, notes: str | None = None) -> dict[str, Any]:
        app = self.db.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")

        app.approval_decision = "approve"
        app.approval_notes = notes
        app.status = ApplicationStatus.APPROVED
        if app.job:
            app.job.status = JobStatus.APPROVED

        send_result = self.email_provider.send(
            to_address=app.email_to or "",
            subject=app.email_subject or "",
            body=app.email_body or "",
        )

        app.status = ApplicationStatus.SENT
        app.sent_at = datetime.now(timezone.utc)
        if app.job:
            app.job.status = JobStatus.SENT
        self.db.commit()

        return {
            "application_id": application_id,
            "status": app.status,
            "send_result": send_result,
        }

    def reject_application(self, application_id: str, notes: str | None = None) -> dict[str, Any]:
        app = self.db.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")

        app.approval_decision = "reject"
        app.approval_notes = notes
        app.status = ApplicationStatus.REJECTED
        if app.job:
            app.job.status = JobStatus.REJECTED
        self.db.commit()
        return {"application_id": application_id, "status": app.status}

    def follow_up(self, application_id: str, days_since_sent: int = 5) -> dict[str, Any]:
        app = self.db.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")

        result = self.app_agents["follow_up_agent"].run(
            application_id=application_id,
            days_since_sent=days_since_sent,
        )
        send_result = self.email_provider.send(
            to_address=app.email_to or "",
            subject=f"Re: {app.email_subject or 'Application follow-up'}",
            body=result["follow_up_body"],
        )
        app.status = ApplicationStatus.FOLLOW_UP_SCHEDULED
        if app.job:
            app.job.status = JobStatus.FOLLOW_UP
        self.db.commit()
        return {"application_id": application_id, "follow_up": result, "send_result": send_result}

    def _candidate_payload(self, candidate: Candidate) -> dict[str, Any]:
        return {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "headline": candidate.headline,
            "location": candidate.location,
            "resume_text": candidate.resume_text,
            "skills": candidate.skills or [],
            "experience": candidate.experience or [],
            "preferences": candidate.preferences or {},
        }

    def _contact_payload(self, contact_id: str | None) -> dict[str, Any] | None:
        if not contact_id:
            return None
        contact = self.db.get(Contact, contact_id)
        if not contact:
            return None
        return {
            "id": contact.id,
            "name": contact.name,
            "email": contact.email,
            "role": contact.role,
            "linkedin_url": contact.linkedin_url,
        }
