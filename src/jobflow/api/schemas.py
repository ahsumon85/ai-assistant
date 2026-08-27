from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_admin: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Candidate ---

class CandidateCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    headline: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    resume_text: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    headline: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    resume_text: str | None = None
    skills: list[str] | None = None
    experience: list[dict[str, Any]] | None = None
    preferences: dict[str, Any] | None = None


class CandidateOut(CandidateCreate):
    id: str
    user_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    title: str
    source: str
    location: str | None = None
    remote_type: str | None = None
    status: str
    match_score: float | None = None
    match_reasons: list[str] | None = None
    missing_skills: list[str] | None = None
    url: str | None = None
    company_id: str | None = None
    company_name: str | None = None
    description: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    status: str
    email_to: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    tailored_resume: str | None = None
    cover_letter: str | None = None
    match_score: float | None = None
    job_title: str | None = None
    company_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmailSyncRequest(BaseModel):
    limit: int | None = 50
    unseen_only: bool = True
    source: str = "all"  # all | linkedin | indeed
    folder: str | None = None
    mark_read: bool | None = None
    date_from: date | None = None
    date_to: date | None = None


class ProcessJobRequest(BaseModel):
    candidate_id: str | None = None
    contact_id: str | None = None
    async_mode: bool = False


class ApprovalRequest(BaseModel):
    notes: str | None = None


class DashboardStats(BaseModel):
    total_jobs: int
    new_jobs: int
    matched_jobs: int
    rejected_jobs: int
    awaiting_approval: int
    sent_applications: int
    pending_tasks: int


class BackgroundTaskOut(BaseModel):
    id: str
    task_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class IntegrationStatus(BaseModel):
    gmail_connected: bool
    outlook_connected: bool
    gmail_email: str | None = None
    outlook_email: str | None = None
