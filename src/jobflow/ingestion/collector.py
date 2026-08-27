from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobflow.db.models import Company, Job, JobStatus
from jobflow.ingestion.email_parsers import parse_email_message
from jobflow.ingestion.normalize import (
    JobDeduper,
    JobNormalizer,
    NormalizedJob,
    RawJob,
    parse_webhook_payload,
)


class JobCollector:
    """Ingest jobs from email alerts, webhooks/APIs, and ATS payloads."""

    def __init__(self, db: Session):
        self.db = db
        self.normalizer = JobNormalizer()

    def collect_raw(self, raw_jobs: list[RawJob]) -> dict[str, Any]:
        deduper = self._build_deduper()
        inserted: list[str] = []
        skipped = 0

        for raw in raw_jobs:
            normalized = self.normalizer.normalize(raw)
            if deduper.is_duplicate(normalized):
                skipped += 1
                continue
            job = self._persist(normalized)
            deduper.remember(normalized)
            inserted.append(job.id)

        self.db.commit()
        return {"inserted": inserted, "skipped_duplicates": skipped, "total": len(raw_jobs)}

    def collect_webhook(self, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        items = payload if isinstance(payload, list) else [payload]
        raw_jobs = [parse_webhook_payload(item) for item in items]
        return self.collect_raw(raw_jobs)

    def collect_email_message(
        self,
        subject: str,
        body: str,
        from_address: str = "",
        message_id: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        jobs = parse_email_message(subject, body, from_address, message_id, source)
        return self.collect_raw(jobs)

    def collect_from_file(self, path: str | Path) -> dict[str, Any]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return self.collect_webhook(data)

    def _build_deduper(self) -> JobDeduper:
        hashes = set(self.db.scalars(select(Job.content_hash)).all())
        keys = {
            (source, external_id)
            for source, external_id in self.db.execute(
                select(Job.source, Job.external_id).where(Job.external_id.is_not(None))
            )
        }
        return JobDeduper(hashes, keys)

    def _persist(self, job: NormalizedJob) -> Job:
        company = self.db.scalar(select(Company).where(Company.name == job.company_name))
        if company is None:
            company = Company(
                name=job.company_name,
                website=job.company_website,
                ats_type=job.ats_type,
            )
            self.db.add(company)
            self.db.flush()
        elif job.company_website and not company.website:
            company.website = job.company_website
        if job.ats_type and not company.ats_type:
            company.ats_type = job.ats_type

        record = Job(
            company_id=company.id,
            source=job.source,
            external_id=job.external_id,
            title=job.title,
            location=job.location,
            remote_type=job.remote_type,
            employment_type=job.employment_type,
            description=job.description,
            requirements=job.requirements,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            currency=job.currency,
            url=job.url,
            posted_at=job.posted_at,
            content_hash=job.content_hash,
            status=JobStatus.NEW,
            raw_payload=job.raw_payload,
        )
        self.db.add(record)
        self.db.flush()
        return record
