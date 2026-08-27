from __future__ import annotations

from fastapi import APIRouter, Depends

from jobflow.api.dependencies import get_candidate_service
from jobflow.api.schemas import CandidateCreate, CandidateOut, CandidateUpdate
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import Candidate, User
from jobflow.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateOut)
def create_candidate(
    payload: CandidateCreate,
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> Candidate:
    return service.create(user, payload)


@router.get("/me", response_model=CandidateOut | None)
def my_candidate(
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> Candidate | None:
    return service.get_for_user(user)


@router.put("/me", response_model=CandidateOut)
def update_my_candidate(
    payload: CandidateUpdate,
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> Candidate:
    return service.update_for_user(user, payload)
