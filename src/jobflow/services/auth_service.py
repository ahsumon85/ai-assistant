from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from jobflow.api.schemas import CandidateCreate, CandidateUpdate, UserLogin, UserRegister
from jobflow.auth.security import create_access_token, hash_password, verify_password
from jobflow.db.models import Candidate, User
from jobflow.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from jobflow.repositories.candidate_repository import CandidateRepository
from jobflow.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._candidates = CandidateRepository(db)
        self._db = db

    def register(self, payload: UserRegister) -> str:
        if self._users.get_by_email(payload.email):
            raise ConflictError("Email already registered")
        user = User(
            id=str(uuid4()),
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        self._users.create(user)
        self._db.add(
            Candidate(
                id=str(uuid4()),
                user_id=user.id,
                full_name=payload.full_name or payload.email.split("@", 1)[0],
                email=payload.email,
            )
        )
        self._users.commit()
        return create_access_token(user.id)

    def login(self, payload: UserLogin) -> str:
        user = self._users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")
        if not user.is_active:
            raise ForbiddenError("Account disabled")
        return create_access_token(user.id)
