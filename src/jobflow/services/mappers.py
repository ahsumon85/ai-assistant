"""Map ORM models to API response schemas."""

from __future__ import annotations

from jobflow.api.schemas import ApplicationOut, JobOut
from jobflow.db.models import Application, Job


def job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        source=job.source,
        location=job.location,
        remote_type=job.remote_type,
        status=job.status,
        match_score=job.match_score,
        match_reasons=job.match_reasons,
        missing_skills=job.missing_skills,
        url=job.url,
        company_id=job.company_id,
        company_name=job.company.name if job.company else None,
        description=job.description,
        created_at=job.created_at,
    )


def application_to_out(app: Application) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        job_id=app.job_id,
        candidate_id=app.candidate_id,
        status=app.status,
        email_to=app.email_to,
        email_subject=app.email_subject,
        email_body=app.email_body,
        tailored_resume=app.tailored_resume,
        cover_letter=app.cover_letter,
        match_score=app.job.match_score if app.job else None,
        job_title=app.job.title if app.job else None,
        company_name=app.job.company.name if app.job and app.job.company else None,
        created_at=app.created_at,
    )
