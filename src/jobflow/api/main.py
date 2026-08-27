from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from jobflow import __version__
from jobflow.api.controllers import (
    application_router,
    auth_router,
    candidate_router,
    dashboard_router,
    health_router,
    ingestion_router,
    integration_router,
    job_router,
    task_router,
)
from jobflow.config import get_settings
from jobflow.db import SessionLocal, init_db
from jobflow.exceptions import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from jobflow.logging_config import setup_logging
from jobflow.services.bootstrap import ensure_default_admin, ensure_default_candidate

setup_logging()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


def _domain_error_status(exc: DomainError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, UnauthorizedError):
        return 401
    if isinstance(exc, ForbiddenError):
        return 403
    if isinstance(exc, ValidationError):
        return 400
    return 400


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        ensure_default_candidate(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="JobFlow",
    description="AI-powered job matching and application assistant",
    version=__version__,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=_domain_error_status(exc), content={"detail": exc.message})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(candidate_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api")
app.include_router(job_router, prefix="/api")
app.include_router(task_router, prefix="/api")
app.include_router(application_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(integration_router, prefix="/api")


@app.get("/")
@limiter.limit(settings.rate_limit)
def root(request: Request) -> dict[str, str]:
    return {
        "name": "JobFlow",
        "version": __version__,
        "docs": "/docs",
        "frontend": settings.frontend_url,
    }
