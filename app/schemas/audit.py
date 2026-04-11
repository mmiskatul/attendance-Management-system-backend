"""Audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import PaginationMeta


class AuditLogResponse(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    campus_id: str | None
    actor_id: str
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    pagination: PaginationMeta
