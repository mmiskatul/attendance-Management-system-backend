"""Student repository."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.student import StudentDocument
from app.repositories.base import MongoRepository
from app.utils.time import utc_now


class StudentRepository(MongoRepository):
    """MongoDB repository for students."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["students"]

    async def create(self, student: StudentDocument) -> StudentDocument:
        payload = self.serialize_document(student.model_dump(by_alias=True, exclude_none=True))
        result = await self.collection.insert_one(payload)
        payload["_id"] = str(result.inserted_id)
        return StudentDocument.model_validate(payload)

    async def get_by_student_id(self, tenant_id: str, student_id: str) -> StudentDocument | None:
        document = await self.collection.find_one({"tenant_id": tenant_id, "student_id": student_id})
        normalized = self.normalize_document(document)
        return StudentDocument.model_validate(normalized) if normalized else None

    async def get_by_barcode(self, tenant_id: str, barcode_value: str) -> StudentDocument | None:
        document = await self.collection.find_one({"tenant_id": tenant_id, "barcode_value": barcode_value})
        normalized = self.normalize_document(document)
        return StudentDocument.model_validate(normalized) if normalized else None

    async def increment_embedding_count(self, tenant_id: str, student_id: str, increment: int) -> None:
        await self.collection.update_one(
            {"tenant_id": tenant_id, "student_id": student_id},
            {"$inc": {"face_embedding_count": increment}, "$set": {"updated_at": utc_now()}},
        )
