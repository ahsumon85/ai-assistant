from __future__ import annotations

from typing import Any

from jobflow.agents.base import BaseAgent
from jobflow.db.models import Application, Job
from jobflow.services.llm import LLMClient


class ResumeAgent(BaseAgent):
    name = "resume_agent"

    def execute(
        self,
        *,
        job_id: str | None = None,
        application_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        assert job_id and candidate is not None
        job = self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        skills = ", ".join(candidate.get("skills") or [])
        fallback = (
            f"{candidate.get('full_name')}\n{candidate.get('email')}\n\n"
            f"TARGET ROLE: {job.title}\n\n"
            f"SUMMARY\nExperienced professional targeting {job.title} with strengths in {skills}.\n\n"
            f"SELECTED EXPERIENCE\n{(candidate.get('resume_text') or 'See attached resume.')[:2000]}\n\n"
            f"SKILLS\n{skills}"
        )

        tailored = self.llm.complete_text(
            system="You rewrite resumes to match a job. Keep facts truthful. Return plain text only.",
            user=(
                f"Job title: {job.title}\nJob description: {job.description[:2500]}\n"
                f"Missing skills to de-emphasize gaps carefully: {(job.missing_skills or [])}\n"
                f"Candidate resume:\n{candidate.get('resume_text')}"
            ),
            fallback=fallback,
        )

        if application_id:
            app = self.db.get(Application, application_id)
            if app:
                app.tailored_resume = tailored
                self.db.flush()

        return {"tailored_resume": tailored}


class CoverLetterAgent(BaseAgent):
    name = "cover_letter_agent"

    def execute(
        self,
        *,
        job_id: str | None = None,
        application_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        research: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        assert job_id and candidate is not None
        job = self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        company_name = job.company.name if job.company else "the company"
        talking_points = (research or {}).get("talking_points") or []
        fallback = (
            f"Dear Hiring Team,\n\n"
            f"I am writing to apply for the {job.title} role at {company_name}. "
            f"My background in {', '.join((candidate.get('skills') or [])[:5])} aligns well with this position. "
            f"{talking_points[0] if talking_points else ''}\n\n"
            f"I would welcome the chance to discuss how I can contribute.\n\n"
            f"Best regards,\n{candidate.get('full_name')}"
        )

        letter = self.llm.complete_text(
            system="Write a concise, professional cover letter. Return plain text only.",
            user=(
                f"Candidate: {candidate.get('full_name')}\nJob: {job.title} at {company_name}\n"
                f"Research: {research}\nResume excerpt: {(candidate.get('resume_text') or '')[:1500]}"
            ),
            fallback=fallback,
        )

        if application_id:
            app = self.db.get(Application, application_id)
            if app:
                app.cover_letter = letter
                self.db.flush()

        return {"cover_letter": letter}


class RecruiterAgent(BaseAgent):
    name = "recruiter_agent"

    def execute(
        self,
        *,
        job_id: str | None = None,
        application_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        research: dict[str, Any] | None = None,
        contact: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        assert job_id and candidate is not None
        job = self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        company_name = job.company.name if job.company else "the company"
        contact_name = (contact or {}).get("name") or "there"
        fallback_notes = (
            f"Target recruiter/contact: {contact_name}. Lead with relevant impact, "
            f"mention {job.title} at {company_name}, and ask for a short intro chat."
        )
        fallback_email = (
            f"Hi {contact_name},\n\n"
            f"I'm {candidate.get('full_name')}, interested in the {job.title} role at {company_name}. "
            f"I'd love to share a brief overview of my background and learn more about the team.\n\n"
            f"Would you be open to a quick chat this week?\n\nThanks,\n{candidate.get('full_name')}"
        )

        notes = self.llm.complete_text(
            system="You advise on recruiter outreach strategy. Return plain text notes.",
            user=f"Job: {job.title}\nCompany research: {research}\nContact: {contact}",
            fallback=fallback_notes,
        )
        subject = f"Interest in {job.title} at {company_name}"
        body = self.llm.complete_text(
            system="Write a short recruiter outreach email. Return plain text only.",
            user=(
                f"Candidate: {candidate.get('full_name')}\nContact: {contact_name}\n"
                f"Job: {job.title} at {company_name}\nStrategy notes: {notes}"
            ),
            fallback=fallback_email,
        )

        if application_id:
            app = self.db.get(Application, application_id)
            if app:
                app.recruiter_notes = notes
                app.email_subject = subject
                app.email_body = body
                if contact and contact.get("email"):
                    app.email_to = contact["email"]
                self.db.flush()

        return {
            "recruiter_notes": notes,
            "email_subject": subject,
            "email_body": body,
            "email_to": (contact or {}).get("email"),
        }


class EmailAgent(BaseAgent):
    name = "email_agent"

    def execute(
        self,
        *,
        application_id: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        assert application_id
        app = self.db.get(Application, application_id)
        if not app:
            raise ValueError(f"Application not found: {application_id}")

        # Prefer recruiter outreach; fall back to cover letter package
        subject = app.email_subject or f"Application: {app.job.title if app.job else 'Role'}"
        body = app.email_body
        if not body:
            body = (
                f"{app.cover_letter or ''}\n\n"
                f"---\nTailored resume attached / included below:\n\n{app.tailored_resume or ''}"
            ).strip()

        app.email_subject = subject
        app.email_body = body
        if not app.email_to and app.job and app.job.company and app.job.company.website:
            # placeholder routing when no contact email exists
            app.email_to = f"careers@{app.job.company.name.lower().replace(' ', '')}.example"
        self.db.flush()

        return {
            "email_to": app.email_to,
            "email_subject": app.email_subject,
            "email_body": app.email_body,
        }


class FollowUpAgent(BaseAgent):
    name = "follow_up_agent"

    def execute(
        self,
        *,
        application_id: str | None = None,
        days_since_sent: int = 5,
        **_: Any,
    ) -> dict[str, Any]:
        assert application_id
        app = self.db.get(Application, application_id)
        if not app:
            raise ValueError(f"Application not found: {application_id}")

        company = app.job.company.name if app.job and app.job.company else "the team"
        fallback = (
            f"Hi,\n\nJust following up on my application for the "
            f"{app.job.title if app.job else 'role'} at {company}. "
            f"Happy to provide any additional information.\n\nBest,\n{app.candidate.full_name if app.candidate else ''}"
        )
        follow_up = self.llm.complete_text(
            system="Write a polite follow-up email. Return plain text only.",
            user=f"Original subject: {app.email_subject}\nDays since sent: {days_since_sent}",
            fallback=fallback,
        )
        app.follow_up_notes = follow_up
        self.db.flush()
        return {"follow_up_body": follow_up, "days_since_sent": days_since_sent}


def build_application_agents(db, llm: LLMClient | None = None) -> dict[str, BaseAgent]:
    llm = llm or LLMClient()
    return {
        "resume_agent": ResumeAgent(db, llm),
        "cover_letter_agent": CoverLetterAgent(db, llm),
        "recruiter_agent": RecruiterAgent(db, llm),
        "email_agent": EmailAgent(db, llm),
        "follow_up_agent": FollowUpAgent(db, llm),
    }
