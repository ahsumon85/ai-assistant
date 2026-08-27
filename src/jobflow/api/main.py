from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from jobflow import __version__
from jobflow.api.auth_routes import router as auth_router
from jobflow.api.dashboard_routes import router as dashboard_router
from jobflow.api.integration_routes import router as integration_router
from jobflow.api.routes import router
from jobflow.config import get_settings
from jobflow.db import SessionLocal, init_db
from jobflow.logging_config import setup_logging
from jobflow.services.bootstrap import ensure_default_admin, ensure_default_candidate

setup_logging()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")
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
