from __future__ import annotations

from sqlalchemy import select

from jobflow.db.models import OAuthToken
from jobflow.repositories.base import BaseRepository


class OAuthTokenRepository(BaseRepository):
    def get_by_user_and_provider(self, user_id: str, provider: str) -> OAuthToken | None:
        return self.db.scalar(
            select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == provider)
        )

    def upsert(self, token: OAuthToken, existing: OAuthToken | None) -> OAuthToken:
        if existing:
            existing.access_token = token.access_token
            existing.refresh_token = token.refresh_token or existing.refresh_token
            existing.token_expiry = token.token_expiry
            self.db.commit()
            return existing
        self.db.add(token)
        self.db.commit()
        return token
