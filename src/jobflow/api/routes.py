from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from jobflow.agents.supervisor import SupervisorAgent
from jobflow.api.schemas import (
    ApprovalRequest,
    ApplicationOut,
    BackgroundTaskOut,
    CandidateCreate,
    CandidateOut,
    CandidateUpdate,
    EmailSyncRequest,
    JobOut,
    ProcessJobRequest,
)
from jobflow.auth.dependencies import get_current_user
from jobflow.db import get_db
from jobflow.db.models import Application, BackgroundTask, Candidate, Job, User
from jobflow.ingestion.collector import JobCollector
from jobflow.ingestion.email_client import ImapJobEmailClient
from jobflow.ingestion.email_sync import sync_jobs_from_email, sync_linkedin_emails
from jobflow.services.bootstrap import create_background_task
from jobflow.workers.tasks import enqueue_task

logger = logging.getLogger(__name__)
router = APIRouter(tags=["core"])


def _job_to_out(job: Job) -> JobOut:
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


def _app_to_out(app: Application) -> ApplicationOut:
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


def _get_user_candidate(db: Session, user: User) -> Candidate | None:
    return db.scalar(select(Candidate).where(Candidate.user_id == user.id))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/llm")
def health_llm() -> dict[str, Any]:
    from jobflow.services.llm import LLMClient

    return LLMClient().status()


@router.post("/candidates", response_model=CandidateOut)
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Candidate:
    existing = db.scalar(select(Candidate).where(Candidate.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Candidate email already exists")
    candidate = Candidate(**payload.model_dump(), user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/candidates/me", response_model=CandidateOut | None)
def my_candidate(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Candidate | None:
    return _get_user_candidate(db, user)


@router.put("/candidates/me", response_model=CandidateOut)
def update_my_candidate(
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Candidate:
    candidate = _get_user_candidate(db, user)
    if not candidate:
        raise HTTPException(status_code=404, detail="Create a candidate profile first")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, key, value)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/ingest/webhook")
async def ingest_webhook(
    payload: dict[str, Any] | list[dict[str, Any]],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    from jobflow.config import get_settings

    settings = get_settings()
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return JobCollector(db).collect_webhook(payload)


@router.get("/ingest/email/status")
def email_ingest_status(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return ImapJobEmailClient().status()


@router.post("/ingest/email/sync")
def sync_email_jobs(
    payload: EmailSyncRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.source == "linkedin" and not payload.unseen_only:
        result = sync_linkedin_emails(
            db,
            limit=payload.limit,
            folder=payload.folder,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
    else:
        result = sync_jobs_from_email(
            db,
            limit=payload.limit,
            unseen_only=payload.unseen_only,
            source_filter=payload.source,
            folder=payload.folder,
            mark_read=payload.mark_read,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobOut]:
    stmt = select(Job).options(joinedload(Job.company)).order_by(Job.created_at.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    jobs = list(db.scalars(stmt).unique().all())
    return [_job_to_out(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobOut:
    job = db.scalar(select(Job).options(joinedload(Job.company)).where(Job.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_out(job)


@router.post("/jobs/{job_id}/process")
async def process_job(
    job_id: str,
    payload: ProcessJobRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    candidate_id = payload.candidate_id
    if not candidate_id:
        candidate = _get_user_candidate(db, user)
        if not candidate:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Create a candidate profile first",
                    "hint": "Open My Profile, add your resume and skills, then run match again.",
                },
            )
        candidate_id = candidate.id

    if payload.async_mode:
        task = create_background_task(
            db,
            task_type="process_job",
            payload={"job_id": job_id, "candidate_id": candidate_id, "contact_id": payload.contact_id},
            user_id=user.id,
        )
        db.commit()
        await enqueue_task("process_job", task.id, job_id=job_id, candidate_id=candidate_id, contact_id=payload.contact_id)
        return {"status": "queued", "task_id": task.id}

    try:
        return SupervisorAgent(db, user_id=user.id).process_job(job_id, candidate_id, payload.contact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}", response_model=BackgroundTaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> BackgroundTask:
    task = db.get(BackgroundTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/applications", response_model=list[ApplicationOut])
def list_applications(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApplicationOut]:
    stmt = select(Application).options(joinedload(Application.job).joinedload(Job.company)).order_by(Application.created_at.desc())
    if status:
        stmt = stmt.where(Application.status == status)
    apps = list(db.scalars(stmt).unique().all())
    return [_app_to_out(a) for a in apps]


@router.get("/applications/{application_id}/approval-queue")
def approval_detail(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    app = db.scalar(
        select(Application)
        .options(joinedload(Application.job).joinedload(Job.company))
        .where(Application.id == application_id)
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
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


@router.post("/applications/{application_id}/approve")
def approve(
    application_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return SupervisorAgent(db, user_id=user.id).approve_application(application_id, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/applications/{application_id}/reject")
def reject(
    application_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return SupervisorAgent(db, user_id=user.id).reject_application(application_id, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
