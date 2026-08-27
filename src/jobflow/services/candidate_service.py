from __future__ import annotations

from sqlalchemy.orm import Session

from jobflow.api.schemas import CandidateCreate, CandidateUpdate
from jobflow.db.models import Candidate, User
from jobflow.exceptions import ConflictError, NotFoundError
from jobflow.repositories.candidate_repository import CandidateRepository


class CandidateService:
    def __init__(self, db: Session) -> None:
        self._repo = CandidateRepository(db)

    def create(self, user: User, payload: CandidateCreate) -> Candidate:
        if self._repo.get_by_email(payload.email):
            raise ConflictError("Candidate email already exists")
        candidate = Candidate(**payload.model_dump(), user_id=user.id)
        return self._repo.create(candidate)

    def get_for_user(self, user: User) -> Candidate | None:
        return self._repo.get_by_user_id(user.id)

    def update_for_user(self, user: User, payload: CandidateUpdate) -> Candidate:
        candidate = self._repo.get_by_user_id(user.id)
        if not candidate:
            raise NotFoundError("Create a candidate profile first")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(candidate, key, value)
        return self._repo.update(candidate)

    def get_or_raise_for_user(self, user: User) -> Candidate:
        candidate = self._repo.get_by_user_id(user.id)
        if not candidate:
            raise NotFoundError(
                {
                    "message": "Create a candidate profile first",
                    "hint": "Open My Profile, add your resume and skills, then run match again.",
                }
            )
        return candidate
