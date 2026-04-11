"""Audit repository."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.audit import AuditLogDocument
from app.repositories.base import MongoRepository


class AuditRepository(MongoRepository):
    """MongoDB repository for audit logs."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["audit_logs"]

    async def create(self, audit_log: AuditLogDocument) -> AuditLogDocument:
        payload = self.serialize_document(audit_log.model_dump(by_alias=True, exclude_none=True))
        result = await self.collection.insert_one(payload)
        payload["_id"] = str(result.inserted_id)
        return AuditLogDocument.model_validate(payload)

    async def list_logs(
        self,
        tenant_id: str,
        *,
        skip: int,
        limit: int,
    ) -> list[AuditLogDocument]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("created_at", -1).skip(skip).limit(limit)
        return [AuditLogDocument.model_validate(self.normalize_document(document)) async for document in cursor]
