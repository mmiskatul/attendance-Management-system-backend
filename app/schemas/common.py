"""Shared API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    skip: int
    limit: int
    returned: int


class ErrorEnvelope(BaseModel):
    """Structured error response envelope."""

    error: dict[str, object]


class RequestContextResponse(BaseModel):
    """Base response metadata."""

    request_id: str | None = None
    timestamp: datetime | None = None


class ORMBaseModel(BaseModel):
    """Base schema with attribute-based validation enabled."""

    model_config = ConfigDict(from_attributes=True)
