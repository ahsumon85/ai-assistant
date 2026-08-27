from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from jobflow.ingestion.collector import JobCollector
from jobflow.ingestion.email_client import ImapConnectionError, ImapJobEmailClient
from jobflow.ingestion.email_parsers import detect_source, parse_email_message
from jobflow.ingestion.normalize import RawJob

logger = logging.getLogger(__name__)


def sync_jobs_from_email(
    db: Session,
    *,
    limit: int | None = None,
    unseen_only: bool = True,
    source_filter: str = "all",
    folder: str | None = None,
    mark_read: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Fetch job alert emails via IMAP and ingest into the database."""
    from jobflow.ingestion.email_client import SourceFilter

    client = ImapJobEmailClient()
    if not client.configured:
        return {
            "status": "error",
            "detail": "IMAP not configured. Set IMAP_USER and IMAP_PASSWORD in .env",
            "emails_fetched": 0,
            "jobs_inserted": 0,
        }

    sf: SourceFilter = "all"
    if source_filter in ("linkedin", "indeed", "all"):
        sf = source_filter  # type: ignore[assignment]

    try:
        emails = client.fetch_job_emails(
            limit=limit,
            unseen_only=unseen_only,
            source_filter=sf,
            folder=folder,
            mark_read=mark_read,
            date_from=date_from,
            date_to=date_to,
        )
    except ImapConnectionError as exc:
        return {
            "status": "error",
            "detail": str(exc),
            "hint": exc.hint,
            "emails_fetched": 0,
            "jobs_inserted": 0,
        }
    collector = JobCollector(db)

    all_raw: list[RawJob] = []
    parsed_by_source: dict[str, int] = {}

    for mail in emails:
        detected = detect_source(mail.from_address, mail.subject)
        jobs = parse_email_message(
            mail.subject,
            mail.body,
            from_address=mail.from_address,
            message_id=mail.message_id,
        )
        all_raw.extend(jobs)
        parsed_by_source[detected] = parsed_by_source.get(detected, 0) + len(jobs)
        logger.info("Parsed %d job(s) from email: %s", len(jobs), mail.subject[:80])

    if not all_raw:
        return {
            "status": "ok",
            "emails_fetched": len(emails),
            "jobs_inserted": 0,
            "skipped_duplicates": 0,
            "parsed_by_source": parsed_by_source,
            "detail": "No new job emails found",
        }

    result = collector.collect_raw(all_raw)
    return {
        "status": "ok",
        "emails_fetched": len(emails),
        "jobs_parsed": len(all_raw),
        "jobs_inserted": len(result["inserted"]),
        "inserted_ids": result["inserted"],
        "skipped_duplicates": result["skipped_duplicates"],
        "parsed_by_source": parsed_by_source,
    }


def sync_linkedin_emails(
    db: Session,
    *,
    limit: int | None = None,
    folder: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Sync ALL LinkedIn job emails (read + unread) from Gmail."""
    from jobflow.config import get_settings

    settings = get_settings()
    return sync_jobs_from_email(
        db,
        limit=limit or settings.imap_linkedin_fetch_limit,
        unseen_only=False,
        source_filter="linkedin",
        folder=folder or settings.imap_folder,
        mark_read=False,
        date_from=date_from,
        date_to=date_to,
    )
