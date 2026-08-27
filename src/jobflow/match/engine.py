from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jobflow.config import get_settings


@dataclass
class MatchResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    passed: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "reasons": self.reasons,
            "missing_skills": self.missing_skills,
            "passed": self.passed,
            "details": self.details,
        }


class MatchEngine:
    """Combine analyzer / fit / company research into a 0–100 match decision."""

    def __init__(self, threshold: int | None = None):
        self.threshold = threshold if threshold is not None else get_settings().match_threshold

    def score(
        self,
        *,
        analysis: dict[str, Any],
        fit: dict[str, Any],
        research: dict[str, Any],
    ) -> MatchResult:
        fit_score = float(fit.get("fit_score") or 0)
        missing = list(fit.get("missing_skills") or [])
        overlap = list(fit.get("overlap_skills") or [])

        reasons = list(fit.get("notes") or [])
        if overlap:
            reasons.append(f" overlapping skills: {', '.join(overlap[:8])}")
        if research.get("talking_points"):
            reasons.append("Company research produced outreach talking points")
        if analysis.get("seniority"):
            reasons.append(f"Role seniority: {analysis['seniority']}")

        # Soft penalty for many missing required skills
        penalty = min(15, len(missing) * 1.5)
        score = max(0.0, min(100.0, fit_score - penalty))

        return MatchResult(
            score=round(score, 1),
            reasons=reasons,
            missing_skills=missing,
            passed=score >= self.threshold,
            details={
                "fit_score": fit_score,
                "penalty": penalty,
                "threshold": self.threshold,
                "role_family": analysis.get("role_family"),
                "company_industry": research.get("industry"),
            },
        )
