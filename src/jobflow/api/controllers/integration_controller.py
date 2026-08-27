from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import RedirectResponse

from jobflow.api.dependencies import get_integration_service
from jobflow.api.schemas import IntegrationStatus
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationStatus)
def integration_status(
    user: User = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> IntegrationStatus:
    return service.get_status(user)


@router.get("/gmail/connect")
def gmail_connect(
    user: User = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> dict[str, str]:
    return {"auth_url": service.gmail_connect_url(user)}


@router.get("/gmail/callback")
def gmail_callback(
    code: str,
    state: str,
    service: IntegrationService = Depends(get_integration_service),
):
    redirect_url = service.gmail_callback(code, state)
    return RedirectResponse(redirect_url)


@router.get("/outlook/connect")
def outlook_connect(
    user: User = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> dict[str, str]:
    return {"auth_url": service.outlook_connect_url(user)}


@router.get("/outlook/callback")
def outlook_callback(
    code: str,
    state: str,
    service: IntegrationService = Depends(get_integration_service),
):
    redirect_url = service.outlook_callback(code, state)
    return RedirectResponse(redirect_url)


@router.post("/webhooks/greenhouse")
async def greenhouse_webhook(
    request: Request,
    async_mode: bool = Query(default=True),
    service: IntegrationService = Depends(get_integration_service),
    x_greenhouse_signature: str | None = Header(default=None),
):
    body = await request.body()
    return await service.greenhouse_webhook(body, x_greenhouse_signature, async_mode)


@router.post("/webhooks/lever")
async def lever_webhook(
    request: Request,
    async_mode: bool = Query(default=True),
    service: IntegrationService = Depends(get_integration_service),
    x_lever_signature: str | None = Header(default=None),
):
    body = await request.body()
    return await service.lever_webhook(body, x_lever_signature, async_mode)
