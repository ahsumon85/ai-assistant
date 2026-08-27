from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print
from sqlalchemy import select

from jobflow.agents.supervisor import SupervisorAgent
from jobflow.db import SessionLocal, init_db
from jobflow.db.models import (
    AgentRun,
    Application,
    BackgroundTask,
    Candidate,
    Company,
    Contact,
    Job,
    OAuthToken,
    User,
)
from jobflow.ingestion.collector import JobCollector

app = typer.Typer(help="JobFlow CLI — ingest, match, and manage applications")


@app.command("init-db")
def init_db_cmd() -> None:
    init_db()
    print("[green]Database tables created.[/green]")


@app.command("clean-db")
def clean_db(
    all_data: bool = typer.Option(
        False,
        "--all",
        help="Also delete users, candidates, and OAuth tokens",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete ingested job data from the database."""
    from sqlalchemy import delete, func, select

    targets: list[tuple[str, type]] = [
        ("agent_runs", AgentRun),
        ("applications", Application),
        ("background_tasks", BackgroundTask),
        ("jobs", Job),
        ("contacts", Contact),
        ("companies", Company),
    ]
    if all_data:
        targets.extend(
            [
                ("oauth_tokens", OAuthToken),
                ("candidates", Candidate),
                ("users", User),
            ]
        )

    db = SessionLocal()
    try:
        counts = {name: db.scalar(select(func.count()).select_from(model)) or 0 for name, model in targets}
        total = sum(counts.values())
        if total == 0:
            print("[yellow]Database is already empty.[/yellow]")
            return

        print("[yellow]Will delete:[/yellow]")
        for name, count in counts.items():
            if count:
                print(f"  {name}: {count}")

        if not yes and not typer.confirm("Continue?"):
            raise typer.Abort()

        deleted: dict[str, int] = {}
        for name, model in targets:
            result = db.execute(delete(model))
            deleted[name] = result.rowcount or 0
        db.commit()

        print("[green]Database cleaned:[/green]")
        for name, count in deleted.items():
            if count:
                print(f"  {name}: {count} deleted")
    finally:
        db.close()


@app.command("sync-email")
def sync_email(
    limit: int = typer.Option(50, help="Max emails to fetch"),
    all_mail: bool = typer.Option(False, help="Include already-read emails"),
    linkedin: bool = typer.Option(False, help="LinkedIn emails only"),
) -> None:
    """Fetch job alert emails from IMAP inbox and ingest jobs."""
    from jobflow.config import get_settings
    from jobflow.ingestion.email_sync import sync_jobs_from_email, sync_linkedin_emails

    db = SessionLocal()
    try:
        if linkedin:
            result = sync_linkedin_emails(db, limit=limit or get_settings().imap_linkedin_fetch_limit)
        else:
            result = sync_jobs_from_email(db, limit=limit, unseen_only=not all_mail)
        print(result)
    finally:
        db.close()


@app.command("ingest")
def ingest(path: Path = typer.Argument(..., exists=True)) -> None:
    db = SessionLocal()
    try:
        print(JobCollector(db).collect_from_file(path))
    finally:
        db.close()


@app.command("process")
def process(
    job_id: str,
    candidate_id: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        if not candidate_id:
            candidate = db.scalar(select(Candidate).limit(1))
            if not candidate:
                raise typer.BadParameter("No candidate found; create one first")
            candidate_id = candidate.id
        result = SupervisorAgent(db).process_job(job_id, candidate_id, contact_id)
        print(result)
    finally:
        db.close()


@app.command("approve")
def approve(application_id: str, notes: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        print(SupervisorAgent(db).approve_application(application_id, notes))
    finally:
        db.close()


@app.command("reject")
def reject(application_id: str, notes: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        print(SupervisorAgent(db).reject_application(application_id, notes))
    finally:
        db.close()


@app.command("list-jobs")
def list_jobs(status: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        stmt = select(Job).order_by(Job.created_at.desc())
        if status:
            stmt = stmt.where(Job.status == status)
        for job in db.scalars(stmt).all():
            score = f"{job.match_score:.0f}" if job.match_score is not None else "-"
            print(f"{job.id} | {job.status:18} | score={score:>3} | {job.title}")
    finally:
        db.close()


@app.command("list-apps")
def list_apps(status: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        stmt = select(Application).order_by(Application.created_at.desc())
        if status:
            stmt = stmt.where(Application.status == status)
        for item in db.scalars(stmt).all():
            print(f"{item.id} | {item.status:20} | job={item.job_id}")
    finally:
        db.close()


if __name__ == "__main__":
    app()
