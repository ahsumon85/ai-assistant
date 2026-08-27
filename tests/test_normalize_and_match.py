from jobflow.ingestion.normalize import JobNormalizer, RawJob, compute_content_hash
from jobflow.match.engine import MatchEngine


def test_normalizer_extracts_basics():
    raw = RawJob(
        source="Greenhouse",
        title="  Senior Backend Engineer  ",
        description="Build APIs with Python and FastAPI. Remote friendly.",
        company_name="Northwind Labs",
        location="Remote - US",
        requirements=["Python", "FastAPI"],
    )
    job = JobNormalizer().normalize(raw)
    assert job.source == "greenhouse"
    assert job.title == "Senior Backend Engineer"
    assert job.remote_type == "remote"
    assert job.content_hash == compute_content_hash(
        title=job.title,
        company_name=job.company_name,
        description=job.description,
        location=job.location,
    )


def test_match_engine_threshold():
    engine = MatchEngine(threshold=70)
    passed = engine.score(
        analysis={"seniority": "senior", "role_family": "engineering", "required_skills": ["python"]},
        fit={
            "fit_score": 88,
            "overlap_skills": ["python", "fastapi"],
            "missing_skills": ["kafka"],
            "notes": ["Strong overlap"],
        },
        research={"talking_points": ["Product-led growth"], "industry": "saas"},
    )
    assert passed.passed is True
    assert passed.score >= 70

    rejected = engine.score(
        analysis={"seniority": "junior"},
        fit={
            "fit_score": 40,
            "overlap_skills": [],
            "missing_skills": ["java", "spring", "kafka", "flink", "scala"],
            "notes": ["Weak overlap"],
        },
        research={},
    )
    assert rejected.passed is False
