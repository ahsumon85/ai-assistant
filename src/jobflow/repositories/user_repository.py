from __future__ import annotations

from sqlalchemy import select

from jobflow.db.models import User
from jobflow.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def commit(self) -> None:
        self.db.commit()
