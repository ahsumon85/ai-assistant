from jobflow.ingestion.email_parsers import (
    detect_source,
    parse_email_message,
    parse_indeed_email,
    parse_linkedin_email,
)


LINKEDIN_SAMPLE = """
Senior Backend Engineer at Northwind Labs
Location: Remote - US

Build Python APIs with FastAPI and PostgreSQL.
https://www.linkedin.com/jobs/view/1234567890

Staff Engineer at Atlas Analytics
Location: New York, NY

Lead platform engineering team.
https://www.linkedin.com/jobs/view/9876543210
"""

INDEED_SAMPLE = """
Backend Developer
Acme Corp
San Francisco, CA

Great opportunity for Python developers.
https://www.indeed.com/viewjob?jk=abc123
"""


def test_detect_linkedin():
    assert detect_source("jobs-noreply@linkedin.com", "New jobs for you") == "linkedin"


def test_detect_indeed():
    assert detect_source("noreply@indeed.com", "New jobs matching your search") == "indeed"


def test_parse_linkedin_subject_hiring_format():
    from jobflow.ingestion.email_parsers import _parse_linkedin_subject

    result = _parse_linkedin_subject("nextjobz is hiring a Software Engineer Backend-Java")
    assert result is not None
    company, title = result
    assert company == "nextjobz"
    assert "Software Engineer" in title

    result2 = _parse_linkedin_subject("MetLife Bangladesh is hiring a Business Analyst (Contractual)")
    assert result2 is not None
    assert result2[0] == "MetLife Bangladesh"


def test_parse_linkedin_from_subject_only():
    jobs = parse_linkedin_email(
        "Senior Flutter Developer – Acme Corp is hiring a Lead Engineer",
        "",
        message_id="msg-li-1",
    )
    assert len(jobs) >= 1
    assert jobs[0].source == "linkedin"
    jobs = parse_linkedin_email("New jobs for you", LINKEDIN_SAMPLE, message_id="msg-1")
    assert len(jobs) >= 2
    assert jobs[0].source == "linkedin"
    assert "Northwind" in jobs[0].company_name or "Backend" in jobs[0].title


def test_parse_indeed_job():
    jobs = parse_indeed_email("Indeed alert", INDEED_SAMPLE, message_id="msg-2")
    assert len(jobs) >= 1
    assert jobs[0].source == "indeed"
    assert jobs[0].url and "indeed.com" in jobs[0].url


def test_parse_email_message_generic():
    body = "Job: Data Engineer\nCompany: DataCo\nLocation: Remote\nhttps://example.com/job/1"
    jobs = parse_email_message("Job alert", body, from_address="hr@dataco.com")
    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    assert jobs[0].company_name == "DataCo"
