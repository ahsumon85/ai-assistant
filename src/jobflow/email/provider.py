from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class SendResult:
    provider: str
    status: str
    detail: str
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "detail": self.detail,
            "message_id": self.message_id,
        }


class EmailProvider(Protocol):
    def send(self, to_address: str, subject: str, body: str) -> dict[str, Any]:
        ...


class DryRunEmailProvider:
    def send(self, to_address: str, subject: str, body: str) -> dict[str, Any]:
        result = SendResult(
            provider="dry_run",
            status="queued",
            detail=f"Dry-run email to={to_address!r} subject={subject!r} ({len(body)} chars)",
            message_id="dry-run-message",
        )
        return result.to_dict()


def get_email_provider() -> EmailProvider:
    return DryRunEmailProvider()
