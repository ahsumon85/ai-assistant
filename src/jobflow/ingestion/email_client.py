from __future__ import annotations

import email
import imaplib
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from email.header import decode_header
from typing import Any, Literal

from jobflow.config import get_settings

logger = logging.getLogger(__name__)

SourceFilter = Literal["linkedin", "indeed", "all"]


class ImapConnectionError(Exception):
    """Raised when IMAP login or fetch fails."""

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


def _quote_mailbox(folder: str) -> str:
    """Quote mailbox name for IMAP SELECT (required when name contains spaces/special chars)."""
    escaped = folder.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _friendly_imap_error(exc: Exception) -> ImapConnectionError:
    raw = str(exc)
    lowered = raw.lower()
    if "application-specific password" in lowered or "app password" in lowered:
        return ImapConnectionError(
            "Gmail requires an App Password, not your regular account password.",
            hint="Enable 2FA on Google, then create an App Password at "
            "https://myaccount.google.com/apppasswords and set IMAP_PASSWORD in .env",
        )
    if "authentication failed" in lowered or "invalid credentials" in lowered:
        return ImapConnectionError(
            "IMAP authentication failed. Check IMAP_USER and IMAP_PASSWORD in .env",
            hint="For Gmail use an App Password; for Outlook ensure IMAP is enabled.",
        )
    if "connection refused" in lowered or "timed out" in lowered:
        return ImapConnectionError(
            f"Could not connect to IMAP server ({get_settings().imap_host}).",
            hint="Check IMAP_HOST, IMAP_PORT, and your network connection.",
        )
    if "could not parse command" in lowered and "select" in lowered:
        folder = get_settings().imap_folder
        return ImapConnectionError(
            f"IMAP could not open folder: {folder!r}",
            hint='Gmail folders with spaces must be quoted in .env, e.g. '
            'IMAP_FOLDER="[Gmail]/All Mail". Try INBOX or "[Gmail]/Social" for LinkedIn alerts.',
        )
    return ImapConnectionError(f"IMAP error: {raw}")


@dataclass
class FetchedEmail:
    subject: str
    body: str
    from_address: str
    message_id: str
    uid: str


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _sender_matches(from_address: str, allowed_senders: list[str]) -> bool:
    if not allowed_senders:
        return True
    from_lower = from_address.lower()
    return any(sender.strip().lower() in from_lower for sender in allowed_senders if sender.strip())


def _subject_matches(subject: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    subject_lower = subject.lower()
    return any(kw.strip().lower() in subject_lower for kw in keywords if kw.strip())


def _format_imap_date(value: date) -> str:
    return value.strftime("%d-%b-%Y")


def _build_imap_search(
    *,
    unseen_only: bool,
    source_filter: SourceFilter,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    parts: list[str] = []
    if unseen_only:
        parts.append("UNSEEN")
    if source_filter == "linkedin":
        parts.append('FROM "linkedin"')
    elif source_filter == "indeed":
        parts.append('FROM "indeed"')
    if date_from:
        parts.append(f"SINCE {_format_imap_date(date_from)}")
    if date_to:
        parts.append(f"BEFORE {_format_imap_date(date_to + timedelta(days=1))}")
    if not parts:
        return "ALL"
    if len(parts) == 1:
        return parts[0]
    return f"({' '.join(parts)})"


class ImapJobEmailClient:
    """Fetch job alert emails from an IMAP inbox (Gmail, Outlook, etc.)."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.imap_user and self.settings.imap_password)

    def fetch_job_emails(
        self,
        *,
        limit: int | None = None,
        unseen_only: bool = True,
        source_filter: SourceFilter = "all",
        folder: str | None = None,
        mark_read: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[FetchedEmail]:
        if not self.configured:
            raise ValueError("IMAP not configured. Set IMAP_USER and IMAP_PASSWORD in .env")

        if source_filter == "linkedin" and limit is None:
            limit = self.settings.imap_linkedin_fetch_limit
        limit = limit or self.settings.imap_fetch_limit

        allowed_senders = self.settings.imap_job_senders_list
        if source_filter == "linkedin":
            allowed_senders = ["linkedin.com", "linkedin", "jobs-noreply@linkedin.com"]
        elif source_filter == "indeed":
            allowed_senders = ["indeed.com", "indeed"]

        subject_keywords = self.settings.imap_subject_keywords_list
        if source_filter == "linkedin":
            # LinkedIn subjects like "Company is hiring a Title" — no generic keyword needed
            subject_keywords = []

        folder = folder or self.settings.imap_folder
        should_mark_read = self.settings.imap_mark_read if mark_read is None else mark_read
        search_criteria = _build_imap_search(
            unseen_only=unseen_only,
            source_filter=source_filter,
            date_from=date_from,
            date_to=date_to,
        )

        if self.settings.imap_use_ssl:
            conn = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        else:
            conn = imaplib.IMAP4(self.settings.imap_host, self.settings.imap_port)

        try:
            conn.login(self.settings.imap_user, self.settings.imap_password)
            status, _ = conn.select(_quote_mailbox(folder))
            if status != "OK":
                raise imaplib.IMAP4.error(f"SELECT command error: BAD [b'Cannot open mailbox {folder}']")

            logger.info("IMAP search folder=%s criteria=%s limit=%d", folder, search_criteria, limit)
            status, data = conn.search(None, search_criteria)
            if status != "OK":
                return []

            uids = data[0].split()
            uids = uids[-limit:] if limit else uids

            results: list[FetchedEmail] = []
            for uid in uids:
                status, msg_data = conn.fetch(uid, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = _decode_header_value(msg.get("Subject"))
                from_address = _decode_header_value(msg.get("From"))
                message_id = msg.get("Message-ID") or uid.decode()

                if not _sender_matches(from_address, allowed_senders):
                    continue
                if not _subject_matches(subject, subject_keywords):
                    continue

                body = _extract_body(msg)
                if not body.strip():
                    body = subject  # LinkedIn subjects often contain the job info

                results.append(
                    FetchedEmail(
                        subject=subject,
                        body=body,
                        from_address=from_address,
                        message_id=message_id,
                        uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                    )
                )

                if should_mark_read:
                    conn.store(uid, "+FLAGS", "\\Seen")

            logger.info("Fetched %d job email(s) from IMAP", len(results))
            return results
        except imaplib.IMAP4.error as exc:
            raise _friendly_imap_error(exc) from exc
        except OSError as exc:
            raise _friendly_imap_error(exc) from exc
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "host": self.settings.imap_host,
            "user": self.settings.imap_user or None,
            "folder": self.settings.imap_folder,
            "senders_filter": self.settings.imap_job_senders_list,
            "subject_keywords": self.settings.imap_subject_keywords_list,
            "linkedin_fetch_limit": self.settings.imap_linkedin_fetch_limit,
        }
