from __future__ import annotations

from sqlalchemy.orm import Session


class BaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
