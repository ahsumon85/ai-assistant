from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from jobflow.agents.base import BaseAgent
from jobflow.db.models import Job, JobStatus
from jobflow.services.llm import LLMClient, extract_skills


class JobAnalyzerAgent(BaseAgent):
    name = "job_analyzer"

    def execute(self, *, job_id: str | None = None, **_: Any) -> dict[str, Any]:
        assert job_id
        job = self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        required = [s.lower() for s in (job.requirements or []) if s]
        if not required:
            required = extract_skills(job.description)[:12]

        fallback = {
            "summary": job.description[:280],
            "required_skills": required,
            "nice_to_have": [],
            "seniority": "senior" if "senior" in job.title.lower() else "mid",
            "role_family": "engineering",
            "key_responsibilities": (job.requirements or [])[:5],
        }

        analysis = self.llm.complete_json(
            system=(
                "You analyze job postings. Return JSON with keys: summary, required_skills, "
                "nice_to_have, seniority, role_family, key_responsibilities."
            ),
            user=f"Title: {job.title}\nDescription: {job.description}",
            fallback=fallback,
        )

        job.analysis = analysis
        job.status = JobStatus.ANALYZED
        self.db.flush()
        return analysis


class JobFitAgent(BaseAgent):
    name = "job_fit"

    def execute(
        self,
        *,
        job_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        assert job_id and candidate is not None
        job = self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        required = [
            str(s).lower()
            for s in ((job.analysis or {}).get("required_skills") or job.requirements or extract_skills(job.description))
        ]
        # Normalize requirement phrases to skill tokens where possible
        job_skills: set[str] = set()
        for item in required:
            extracted = extract_skills(item)
            if extracted:
                job_skills.update(extracted)
            else:
                job_skills.add(item)

        candidate_skills = set(
            s.lower() for s in (candidate.get("skills") or extract_skills(candidate.get("resume_text") or ""))
        )
        overlap = sorted(job_skills & candidate_skills)
        missing = sorted(job_skills - candidate_skills)
        coverage = (len(overlap) / len(job_skills)) if job_skills else 0.5

        prefs = candidate.get("preferences") or {}
        remote_ok = True
        if prefs.get("remote_only") and job.remote_type == "onsite":
            remote_ok = False

        # Weight skill coverage heavily; bonus for remote/location alignment
        base = int(round(coverage * 90))
        if remote_ok:
            base += 5
        if job.location and candidate.get("location"):
            cand_loc = str(candidate.get("location")).lower()
            job_loc = job.location.lower()
            if "remote" in job_loc and "remote" in cand_loc:
                base += 5
            elif job_loc in cand_loc or cand_loc in job_loc:
                base += 5
        score = max(0, min(100, base))

        fallback = {
            "fit_score": score,
            "overlap_skills": overlap,
            "missing_skills": missing,
            "notes": [
                f"Skill coverage {int(coverage * 100)}%",
                "Remote preference matched" if remote_ok else "Remote preference mismatch",
            ],
        }

        return self.llm.complete_json(
            system=(
                "You evaluate candidate-job fit. Return JSON with fit_score (0-100), "
                "overlap_skills, missing_skills, notes."
            ),
            user=(
                f"Job: {job.title}\nAnalysis: {job.analysis}\n"
                f"Candidate skills: {candidate.get('skills')}\nResume: {(candidate.get('resume_text') or '')[:3000]}"
            ),
            fallback=fallback,
        )


class CompanyResearcherAgent(BaseAgent):
    name = "company_researcher"

    def execute(self, *, job_id: str | None = None, **_: Any) -> dict[str, Any]:
        assert job_id
        job = self.db.get(Job, job_id)
        if not job or not job.company:
            raise ValueError(f"Job/company not found: {job_id}")

        company = job.company
        fallback = {
            "overview": company.description
            or f"{company.name} is hiring for {job.title}. Research pending deeper enrichment.",
            "industry": company.industry or "technology",
            "culture_signals": [],
            "talking_points": [
                f"Interest in the {job.title} role",
                f"Alignment with {company.name}'s product direction",
            ],
            "risks": [],
        }

        research = self.llm.complete_json(
            system=(
                "You research companies for job applications. Return JSON with overview, industry, "
                "culture_signals, talking_points, risks."
            ),
            user=(
                f"Company: {company.name}\nWebsite: {company.website}\n"
                f"Job: {job.title}\nDescription excerpt: {job.description[:1500]}"
            ),
            fallback=fallback,
        )

        company.research_notes = research
        if research.get("industry"):
            company.industry = research["industry"]
        if research.get("overview") and not company.description:
            company.description = research["overview"]
        self.db.flush()
        return research


def build_analysis_agents(db: Session, llm: LLMClient | None = None) -> dict[str, BaseAgent]:
    llm = llm or LLMClient()
    return {
        "job_analyzer": JobAnalyzerAgent(db, llm),
        "job_fit": JobFitAgent(db, llm),
        "company_researcher": CompanyResearcherAgent(db, llm),
    }
