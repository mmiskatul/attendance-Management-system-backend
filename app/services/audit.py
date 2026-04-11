"""Audit service."""

from __future__ import annotations

from typing import Any

from app.models.audit import AuditLogDocument
from app.repositories.audit_repository import AuditRepository
from app.utils.pagination import sanitize_pagination
from app.utils.time import utc_now


class AuditService:
    """Write and read audit events."""

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    async def record(
        self,
        *,
        tenant_id: str,
        campus_id: str | None,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogDocument:
        audit_log = AuditLogDocument(
            tenant_id=tenant_id,
            campus_id=campus_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        return await self.repository.create(audit_log)

    async def list_logs(self, tenant_id: str, *, skip: int, limit: int) -> list[AuditLogDocument]:
        safe_skip, safe_limit = sanitize_pagination(skip=skip, limit=limit)
        return await self.repository.list_logs(tenant_id, skip=safe_skip, limit=safe_limit)
