from __future__ import annotations

from fastapi import APIRouter, Depends

from jobflow.api.dependencies import get_auth_service
from jobflow.api.schemas import TokenResponse, UserLogin, UserOut, UserRegister
from jobflow.auth.dependencies import get_current_user
from jobflow.db.models import User
from jobflow.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    token = service.register(payload)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    token = service.login(payload)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
