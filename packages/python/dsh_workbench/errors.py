"""Errors raised by the public DSH Workbench SDK."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SDKError(Exception):
    """Base exception for client and model errors."""


class ModelError(SDKError, ValueError):
    """Raised when a server response cannot be represented by a model."""


@dataclass
class APIError(SDKError):
    status_code: int
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        suffix = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{self.code}: {self.message}{suffix}"


class AuthenticationError(APIError):
    pass


class PermissionError(APIError):
    pass


class NotFoundError(APIError):
    pass


class ConflictError(APIError):
    pass


class ValidationError(APIError):
    pass


class ServerError(APIError):
    pass
