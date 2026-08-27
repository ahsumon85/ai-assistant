from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from jobflow.api.dependencies import get_candidate_service, get_job_service
from jobflow.api.schemas import JobOut, ProcessJobRequest
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.candidate_service import CandidateService
from jobflow.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str | None = None,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobOut]:
    return service.list_jobs(status)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobOut:
    return service.get_job(job_id)


@router.post("/{job_id}/process")
async def process_job(
    job_id: str,
    payload: ProcessJobRequest,
    user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
    candidate_service: CandidateService = Depends(get_candidate_service),
):
    candidate_id = payload.candidate_id
    if not candidate_id:
        candidate = candidate_service.get_or_raise_for_user(user)
        candidate_id = candidate.id
    return await job_service.process_job(
        job_id,
        candidate_id,
        payload.contact_id,
        user.id,
        payload.async_mode,
    )
