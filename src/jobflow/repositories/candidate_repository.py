from __future__ import annotations

from sqlalchemy import select

from jobflow.db.models import Candidate
from jobflow.repositories.base import BaseRepository


class CandidateRepository(BaseRepository):
    def get_by_email(self, email: str) -> Candidate | None:
        return self.db.scalar(select(Candidate).where(Candidate.email == email))

    def get_by_user_id(self, user_id: str) -> Candidate | None:
        return self.db.scalar(select(Candidate).where(Candidate.user_id == user_id))

    def create(self, candidate: Candidate) -> Candidate:
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def update(self, candidate: Candidate) -> Candidate:
        self.db.commit()
        self.db.refresh(candidate)
        return candidate
