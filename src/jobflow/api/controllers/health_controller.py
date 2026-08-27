from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from jobflow.services.llm import LLMClient

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/llm")
def health_llm() -> dict[str, Any]:
    return LLMClient().status()
