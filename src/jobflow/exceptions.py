"""Domain exceptions mapped to HTTP responses in the API layer."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level errors."""

    def __init__(self, message: str | dict) -> None:
        self.message = message
        super().__init__(str(message))


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass
