from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from email.mime.text import MIMEText
from typing import Any

from jobflow.config import get_settings
from jobflow.email.provider import DryRunEmailProvider, SendResult

logger = logging.getLogger(__name__)


def verify_webhook_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret:
        # Dev mode: allow unsigned webhooks when secret not configured
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, provided)


def verify_greenhouse_signature(body: bytes, signature: str | None) -> bool:
    return verify_webhook_signature(get_settings().greenhouse_webhook_secret, body, signature)


def verify_lever_signature(body: bytes, signature: str | None) -> bool:
    return verify_webhook_signature(get_settings().lever_webhook_secret, body, signature)


def normalize_greenhouse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Greenhouse webhook payload to our ingest format."""
    action = payload.get("action")
    if action and action != "job_post_created" and action != "job_post_updated":
        return {}
    job = payload.get("payload", {}).get("job", payload.get("job", payload))
    if not job:
        return {}
    return {
        "source": "greenhouse",
        "ats": "greenhouse",
        "id": str(job.get("id", "")),
        "title": job.get("name") or job.get("title"),
        "description": job.get("content") or job.get("description", ""),
        "company": {"name": job.get("company_name") or payload.get("organization", {}).get("name", "Unknown")},
        "location": (job.get("offices") or [{}])[0].get("name") if job.get("offices") else job.get("location"),
        "url": job.get("absolute_url"),
        "employment_type": job.get("employment_type"),
    }


def normalize_lever_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Lever webhook payload to our ingest format."""
    data = payload.get("data", payload)
    if not data:
        return {}
    return {
        "source": "lever",
        "ats": "lever",
        "id": str(data.get("id", "")),
        "title": data.get("text") or data.get("title"),
        "description": data.get("descriptionPlain") or data.get("description", ""),
        "company": {"name": data.get("company") or "Unknown"},
        "location": (data.get("categories") or {}).get("location"),
        "url": data.get("hostedUrl") or data.get("applyUrl"),
        "employment_type": (data.get("categories") or {}).get("commitment"),
    }


class GmailService:
    """Gmail OAuth + send via Google API."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/userinfo.email"]

    def __init__(self, access_token: str | None = None, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.settings = get_settings()

    def get_auth_url(self, state: str) -> str:
        from urllib.parse import urlencode

        params = urlencode(
            {
                "client_id": self.settings.gmail_client_id,
                "redirect_uri": self.settings.gmail_redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        import httpx

        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.settings.gmail_client_id,
                "client_secret": self.settings.gmail_client_secret,
                "redirect_uri": self.settings.gmail_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def refresh_access_token(self) -> dict[str, Any]:
        import httpx

        if not self.refresh_token:
            raise ValueError("No refresh token")
        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.settings.gmail_client_id,
                "client_secret": self.settings.gmail_client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def send(self, to_address: str, subject: str, body: str, from_address: str | None = None) -> dict[str, Any]:
        if not self.refresh_token and not self.access_token:
            return DryRunEmailProvider().send(to_address, subject, body)

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.gmail_client_id,
                client_secret=self.settings.gmail_client_secret,
            )
            service = build("gmail", "v1", credentials=creds)
            sender = from_address or "me"
            message = MIMEText(body)
            message["to"] = to_address
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return SendResult(
                provider="gmail",
                status="sent",
                detail=f"Sent to {to_address}",
                message_id=sent.get("id"),
            ).to_dict()
        except Exception as exc:
            logger.exception("Gmail send failed")
            return SendResult(provider="gmail", status="error", detail=str(exc)).to_dict()


class OutlookService:
    """Microsoft Graph OAuth + sendMail."""

    SCOPES = "offline_access Mail.Send User.Read"

    def __init__(self, access_token: str | None = None, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.settings = get_settings()

    def get_auth_url(self, state: str) -> str:
        from urllib.parse import urlencode

        params = urlencode(
            {
                "client_id": self.settings.outlook_client_id,
                "redirect_uri": self.settings.outlook_redirect_uri,
                "response_type": "code",
                "scope": self.SCOPES,
                "state": state,
            }
        )
        tenant = self.settings.outlook_tenant_id or "common"
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{params}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        import httpx

        tenant = self.settings.outlook_tenant_id or "common"
        resp = httpx.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": self.settings.outlook_client_id,
                "client_secret": self.settings.outlook_client_secret,
                "code": code,
                "redirect_uri": self.settings.outlook_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def send(self, to_address: str, subject: str, body: str) -> dict[str, Any]:
        if not self.access_token:
            return DryRunEmailProvider().send(to_address, subject, body)

        import httpx

        resp = httpx.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to_address}}],
                }
            },
            timeout=30,
        )
        if resp.status_code in (200, 202):
            return SendResult(provider="outlook", status="sent", detail=f"Sent to {to_address}").to_dict()
        return SendResult(provider="outlook", status="error", detail=resp.text).to_dict()
