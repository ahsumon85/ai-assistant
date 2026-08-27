from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawJob:
    """Job as received from a source before normalization."""

    source: str
    title: str
    description: str
    company_name: str
    external_id: str | None = None
    location: str | None = None
    url: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    company_website: str | None = None
    ats_type: str | None = None
    requirements: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedJob:
    source: str
    external_id: str | None
    title: str
    description: str
    company_name: str
    location: str | None
    url: str | None
    remote_type: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    posted_at: datetime | None
    company_website: str | None
    ats_type: str | None
    requirements: list[str]
    content_hash: str
    raw_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.posted_at:
            data["posted_at"] = self.posted_at.isoformat()
        return data


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _infer_remote_type(location: str | None, description: str) -> str | None:
    blob = f"{location or ''} {description}".lower()
    if "remote" in blob or "work from home" in blob:
        return "remote"
    if "hybrid" in blob:
        return "hybrid"
    if location:
        return "onsite"
    return None


def compute_content_hash(
    *,
    title: str,
    company_name: str,
    description: str,
    location: str | None = None,
) -> str:
    payload = "|".join(
        [
            _clean_text(title).lower(),
            _clean_text(company_name).lower(),
            _clean_text(location).lower(),
            _clean_text(description)[:2000].lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JobNormalizer:
    """Normalize heterogeneous job payloads into a canonical shape."""

    def normalize(self, raw: RawJob) -> NormalizedJob:
        title = _clean_text(raw.title)
        description = _clean_text(raw.description)
        company_name = _clean_text(raw.company_name)
        location = _clean_text(raw.location) or None
        requirements = [_clean_text(r) for r in raw.requirements if _clean_text(r)]

        if not requirements:
            requirements = self._extract_requirements(description)

        content_hash = compute_content_hash(
            title=title,
            company_name=company_name,
            description=description,
            location=location,
        )

        return NormalizedJob(
            source=raw.source.lower(),
            external_id=raw.external_id or content_hash[:16],
            title=title,
            description=description,
            company_name=company_name,
            location=location,
            url=raw.url,
            remote_type=raw.remote_type or _infer_remote_type(location, description),
            employment_type=raw.employment_type,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            currency=raw.currency,
            posted_at=raw.posted_at,
            company_website=raw.company_website,
            ats_type=raw.ats_type,
            requirements=requirements,
            content_hash=content_hash,
            raw_payload=raw.raw_payload
            or {
                "source": raw.source,
                "title": raw.title,
                "company_name": raw.company_name,
                "external_id": raw.external_id,
                "location": raw.location,
                "url": raw.url,
            },
        )

    def _extract_requirements(self, description: str) -> list[str]:
        patterns = [
            r"(?:requirements?|qualifications?|you (?:have|bring)|must have)[:\s]+(.+?)(?:\n\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, flags=re.IGNORECASE | re.DOTALL)
            if match:
                chunk = match.group(1)
                bullets = re.split(r"[•\-\n]+", chunk)
                return [_clean_text(b) for b in bullets if len(_clean_text(b)) > 8][:12]
        return []


class JobDeduper:
    """Skip jobs already stored by content hash or source+external_id."""

    def __init__(self, existing_hashes: set[str], existing_keys: set[tuple[str, str]]):
        self.existing_hashes = existing_hashes
        self.existing_keys = existing_keys

    def is_duplicate(self, job: NormalizedJob) -> bool:
        if job.content_hash in self.existing_hashes:
            return True
        if job.external_id and (job.source, job.external_id) in self.existing_keys:
            return True
        return False

    def remember(self, job: NormalizedJob) -> None:
        self.existing_hashes.add(job.content_hash)
        if job.external_id:
            self.existing_keys.add((job.source, job.external_id))


def parse_webhook_payload(payload: dict[str, Any], default_source: str = "webhook") -> RawJob:
    """Accept flexible webhook/API payloads from Greenhouse, Lever, or custom sources."""
    source = str(payload.get("source") or payload.get("ats") or default_source).lower()
    company = payload.get("company") or {}
    if isinstance(company, str):
        company = {"name": company}

    return RawJob(
        source=source,
        title=str(payload.get("title") or payload.get("job_title") or "Untitled"),
        description=str(payload.get("description") or payload.get("content") or ""),
        company_name=str(company.get("name") or payload.get("company_name") or "Unknown"),
        external_id=str(payload.get("id") or payload.get("external_id") or "") or None,
        location=payload.get("location"),
        url=payload.get("url") or payload.get("absolute_url"),
        remote_type=payload.get("remote_type"),
        employment_type=payload.get("employment_type") or payload.get("type"),
        salary_min=payload.get("salary_min"),
        salary_max=payload.get("salary_max"),
        currency=payload.get("currency"),
        company_website=company.get("website"),
        ats_type=payload.get("ats") or (source if source in {"greenhouse", "lever"} else None),
        requirements=list(payload.get("requirements") or []),
        raw_payload=payload,
    )


def dumps_normalized(jobs: list[NormalizedJob]) -> str:
    return json.dumps([j.to_dict() for j in jobs], indent=2)
