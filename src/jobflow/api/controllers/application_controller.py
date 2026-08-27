from __future__ import annotations

from fastapi import APIRouter, Depends

from jobflow.api.dependencies import get_application_service
from jobflow.api.schemas import ApplicationOut, ApprovalRequest
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.application_service import ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status: str | None = None,
    user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationOut]:
    return service.list_applications(status)


@router.get("/{application_id}/approval-queue")
def approval_detail(
    application_id: str,
    user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
):
    return service.get_approval_detail(application_id)


@router.post("/{application_id}/approve")
def approve(
    application_id: str,
    payload: ApprovalRequest,
    user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
):
    return service.approve(application_id, user.id, payload.notes)


@router.post("/{application_id}/reject")
def reject(
    application_id: str,
    payload: ApprovalRequest,
    user: User = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
):
    return service.reject(application_id, user.id, payload.notes)
