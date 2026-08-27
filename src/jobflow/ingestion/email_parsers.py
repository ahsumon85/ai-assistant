from __future__ import annotations

import html
import re
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any

from jobflow.ingestion.normalize import RawJob


@dataclass
class ParsedEmail:
    subject: str
    body: str
    from_address: str
    message_id: str | None = None


def html_to_text(content: str) -> str:
    """Rough HTML → plain text for email bodies."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", content)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_source(from_address: str, subject: str) -> str:
    blob = f"{from_address} {subject}".lower()
    if "linkedin" in blob:
        return "linkedin"
    if "indeed" in blob:
        return "indeed"
    if "glassdoor" in blob:
        return "glassdoor"
    if "greenhouse" in blob:
        return "greenhouse"
    if "lever.co" in blob or "lever" in blob:
        return "lever"
    if "ziprecruiter" in blob:
        return "ziprecruiter"
    return "email"


def _clean_line(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s<>\"')\]]+", text)


def _job_block_from_lines(
    *,
    source: str,
    title: str,
    company: str,
    location: str | None,
    url: str | None,
    description: str,
    subject: str,
    message_id: str | None,
) -> RawJob:
    return RawJob(
        source=source,
        title=title,
        description=description,
        company_name=company or "Unknown",
        location=location,
        url=url,
        external_id=message_id or url,
        raw_payload={"subject": subject, "snippet": description[:500]},
    )


def _parse_linkedin_subject(subject: str) -> tuple[str, str] | None:
    """Parse 'Company is hiring a Job Title' format from LinkedIn subjects."""
    patterns = [
        r"^(?P<company>.+?)\s+is hiring\s+(?:a|an)\s+(?P<title>.+?)(?:\s*[-–|].*)?$",
        r"^(?P<company>.+?)\s+is hiring\s*:\s*(?P<title>.+)$",
        r"^(?P<title>.+?)\s+(?:at|@)\s+(?P<company>.+?)(?:\s*[-–|].*)?$",
    ]
    subject = subject.strip()
    for pattern in patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            company = _clean_line(match.group("company")) or "Unknown"
            title = _clean_line(match.group("title")) or "Job"
            if len(title) > 3 and len(company) > 1:
                return company, title
    return None


def parse_linkedin_email(subject: str, body: str, message_id: str | None = None) -> list[RawJob]:
    """Parse LinkedIn job alert emails (single or multiple listings)."""
    jobs: list[RawJob] = []
    text = html_to_text(body) if "<" in body else body
    all_urls = [u for u in _extract_urls(text) if "linkedin.com" in u]
    default_url = all_urls[0].rstrip(").,") if all_urls else None

    # Pattern 1: "Title at Company" in body blocks
    blocks = re.split(r"\n{2,}", text)
    for block in blocks:
        block = block.strip()
        if len(block) < 15:
            continue

        title_company = re.search(
            r"(?P<title>[A-Za-z0-9][^\n@]{4,100}?)\s+(?:at|@)\s+(?P<company>[^\n(]{2,80})",
            block,
            re.IGNORECASE,
        )
        hiring_match = re.search(
            r"(?P<company>.+?)\s+is hiring\s+(?:a|an)\s+(?P<title>.+)",
            block,
            re.IGNORECASE,
        )
        if hiring_match:
            company = _clean_line(hiring_match.group("company")) or "Unknown"
            title = _clean_line(hiring_match.group("title")) or "Job"
        elif title_company:
            title = _clean_line(title_company.group("title")) or "Job"
            company = _clean_line(title_company.group("company")) or "Unknown"
        else:
            continue

        if company.endswith(")"):
            company = company.split("(")[0].strip()

        location_match = re.search(r"(?:Location|📍)\s*:?\s*(.+)", block, re.IGNORECASE)
        location = _clean_line(location_match.group(1)) if location_match else None

        urls = [u for u in _extract_urls(block) if "linkedin.com" in u]
        job_url = urls[0].rstrip(").,") if urls else default_url

        jobs.append(
            _job_block_from_lines(
                source="linkedin",
                title=title,
                company=company,
                location=location,
                url=job_url,
                description=block or text,
                subject=subject,
                message_id=f"{message_id}-{len(jobs)}" if message_id else job_url,
            )
        )

    # Pattern 2: parse from subject line (very common for LinkedIn)
    if not jobs:
        parsed = _parse_linkedin_subject(subject)
        if parsed:
            company, title = parsed
            jobs.append(
                _job_block_from_lines(
                    source="linkedin",
                    title=title,
                    company=company,
                    location=None,
                    url=default_url,
                    description=text or subject,
                    subject=subject,
                    message_id=message_id,
                )
            )

    if not jobs:
        title = re.sub(r"^(new jobs matching|job alert|jobs for you)[:\s-]*", "", subject, flags=re.I).strip()
        urls = [u for u in _extract_urls(text) if "linkedin.com" in u]
        jobs.append(
            _job_block_from_lines(
                source="linkedin",
                title=title or "LinkedIn Job Alert",
                company="Unknown",
                location=None,
                url=urls[0].rstrip(").,") if urls else default_url,
                description=text or subject,
                subject=subject,
                message_id=message_id,
            )
        )
    return jobs


def parse_indeed_email(subject: str, body: str, message_id: str | None = None) -> list[RawJob]:
    """Parse Indeed job alert emails."""
    text = html_to_text(body) if "<" in body else body
    all_urls = [u for u in _extract_urls(text) if "indeed.com" in u]
    default_url = all_urls[0].rstrip(").,") if all_urls else None

    jobs: list[RawJob] = []
    blocks = re.split(r"\n{2,}", text)
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue

        title = lines[0]
        if len(title) < 4 or title.lower().startswith(("indeed", "view", "unsubscribe", "great opportunity")):
            continue

        company = lines[1] if len(lines) > 1 and not lines[1].startswith("http") else "Unknown"
        location = None
        for line in lines[2:]:
            if line.startswith("http"):
                break
            location = line
            break

        urls = [u for u in _extract_urls(block) if "indeed.com" in u]
        job_url = urls[0].rstrip(").,") if urls else default_url

        jobs.append(
            _job_block_from_lines(
                source="indeed",
                title=title,
                company=company,
                location=location,
                url=job_url,
                description=text,
                subject=subject,
                message_id=f"{message_id}-{len(jobs)}" if message_id else None,
            )
        )

    if not jobs:
        jobs.append(
            _job_block_from_lines(
                source="indeed",
                title=subject or "Indeed Job Alert",
                company="Unknown",
                location=None,
                url=default_url,
                description=text,
                subject=subject,
                message_id=message_id,
            )
        )
    return jobs


def parse_generic_email(subject: str, body: str, source: str = "email", message_id: str | None = None) -> list[RawJob]:
    """Generic parser for simple job alert formats."""
    text = html_to_text(body) if "<" in body else body
    title_match = re.search(r"(?:Job|Role|Position|Title)\s*:?\s*(.+)", text, re.IGNORECASE)
    company_match = re.search(r"Company\s*:?\s*(.+)", text, re.IGNORECASE)
    location_match = re.search(r"Location\s*:?\s*(.+)", text, re.IGNORECASE)
    urls = _extract_urls(text)

    title = _clean_line(title_match.group(1)) if title_match else _clean_line(subject) or "Job Alert"
    company = _clean_line(company_match.group(1)) if company_match else "Unknown"
    location = _clean_line(location_match.group(1)) if location_match else None

    return [
        _job_block_from_lines(
            source=source,
            title=title,
            company=company,
            location=location,
            url=urls[0].rstrip(").,") if urls else None,
            description=text,
            subject=subject,
            message_id=message_id,
        )
    ]


def parse_email_message(
    subject: str,
    body: str,
    from_address: str = "",
    message_id: str | None = None,
    source: str | None = None,
) -> list[RawJob]:
    """Detect source and parse one email into one or more jobs."""
    detected = source or detect_source(from_address, subject)
    if detected == "linkedin":
        return parse_linkedin_email(subject, body, message_id)
    if detected == "indeed":
        return parse_indeed_email(subject, body, message_id)
    return parse_generic_email(subject, body, source=detected, message_id=message_id)

