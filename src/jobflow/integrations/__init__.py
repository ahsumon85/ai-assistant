from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from sqlalchemy import select

from jobflow.db.models import OAuthToken
from jobflow.email.provider import DryRunEmailProvider, EmailProvider
from jobflow.integrations.email_oauth import GmailService, OutlookService
from jobflow.config import get_settings

logger = logging.getLogger(__name__)


class UserGmailProvider:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        token = db.scalar(
            select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == "gmail")
        )
        self.token = token

    def send(self, to_address: str, subject: str, body: str) -> dict[str, Any]:
        if not self.token or not self.token.refresh_token:
            settings = get_settings()
            if settings.gmail_client_id and settings.email_provider == "gmail":
                logger.warning("Gmail not connected for user %s; falling back to dry-run", self.user_id)
            return DryRunEmailProvider().send(to_address, subject, body)
        return GmailService(
            access_token=self.token.access_token,
            refresh_token=self.token.refresh_token,
        ).send(to_address, subject, body, from_address=self.token.email_address)


class UserOutlookProvider:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        token = db.scalar(
            select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == "outlook")
        )
        self.token = token

    def send(self, to_address: str, subject: str, body: str) -> dict[str, Any]:
        if not self.token or not self.token.access_token:
            return DryRunEmailProvider().send(to_address, subject, body)
        return OutlookService(
            access_token=self.token.access_token,
            refresh_token=self.token.refresh_token,
        ).send(to_address, subject, body)


def get_email_provider_for_user(db: Session, user_id: str | None = None) -> EmailProvider:
    settings = get_settings()
    if user_id:
        if settings.email_provider == "gmail":
            return UserGmailProvider(db, user_id)
        if settings.email_provider == "outlook":
            return UserOutlookProvider(db, user_id)
    return DryRunEmailProvider()
