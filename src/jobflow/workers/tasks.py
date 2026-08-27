from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from jobflow.config import get_settings
from jobflow.db import SessionLocal
from jobflow.services.bootstrap import mark_task_done, mark_task_failed, mark_task_running

logger = logging.getLogger(__name__)


async def process_job_task(ctx: dict, task_id: str, job_id: str, candidate_id: str, contact_id: str | None = None) -> dict[str, Any]:
    from jobflow.agents.supervisor import SupervisorAgent

    db = SessionLocal()
    try:
        mark_task_running(db, task_id)
        db.commit()
        result = SupervisorAgent(db).process_job(job_id, candidate_id, contact_id)
        mark_task_done(db, task_id, result)
        return result
    except Exception as exc:
        logger.exception("process_job_task failed")
        mark_task_failed(db, task_id, str(exc))
        raise
    finally:
        db.close()


async def ingest_webhook_task(ctx: dict, task_id: str, payload: dict | list) -> dict[str, Any]:
    from jobflow.ingestion.collector import JobCollector

    db = SessionLocal()
    try:
        mark_task_running(db, task_id)
        db.commit()
        result = JobCollector(db).collect_webhook(payload)
        mark_task_done(db, task_id, result)
        return result
    except Exception as exc:
        logger.exception("ingest_webhook_task failed")
        mark_task_failed(db, task_id, str(exc))
        raise
    finally:
        db.close()


class WorkerSettings:
    functions = [process_job_task, ingest_webhook_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 600


async def enqueue_task(task_type: str, task_id: str, **kwargs: Any) -> str:
    redis = await create_pool(WorkerSettings.redis_settings)
    if task_type == "process_job":
        await redis.enqueue_job("process_job_task", task_id, kwargs["job_id"], kwargs["candidate_id"], kwargs.get("contact_id"))
    elif task_type == "ingest_webhook":
        await redis.enqueue_job("ingest_webhook_task", task_id, kwargs["payload"])
    else:
        raise ValueError(f"Unknown task type: {task_type}")
    await redis.close()
    return task_id
