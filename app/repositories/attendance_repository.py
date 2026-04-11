"""Attendance repository."""

from __future__ import annotations

from datetime import date

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.attendance import AttendanceRecordDocument
from app.models.common import AttendanceSession
from app.repositories.base import MongoRepository


class AttendanceRepository(MongoRepository):
    """MongoDB repository for attendance records."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["attendance_records"]

    async def create(self, record: AttendanceRecordDocument) -> AttendanceRecordDocument:
        payload = self.serialize_document(record.model_dump(by_alias=True, exclude_none=True))
        result = await self.collection.insert_one(payload)
        payload["_id"] = str(result.inserted_id)
        return AttendanceRecordDocument.model_validate(payload)

    async def get_by_student_and_date(
        self,
        tenant_id: str,
        student_id: str,
        attendance_date: date,
        attendance_session: AttendanceSession,
    ) -> AttendanceRecordDocument | None:
        document = await self.collection.find_one(
            {
                "tenant_id": tenant_id,
                "student_id": student_id,
                "attendance_date": attendance_date.isoformat(),
                "attendance_session": attendance_session,
            }
        )
        normalized = self.normalize_document(document)
        return AttendanceRecordDocument.model_validate(normalized) if normalized else None

    async def list_by_student(
        self,
        tenant_id: str,
        student_id: str,
        *,
        skip: int,
        limit: int,
    ) -> list[AttendanceRecordDocument]:
        cursor = (
            self.collection.find({"tenant_id": tenant_id, "student_id": student_id})
            .sort("check_in_time", -1)
            .skip(skip)
            .limit(limit)
        )
        return [AttendanceRecordDocument.model_validate(self.normalize_document(document)) async for document in cursor]

    async def list_by_day(
        self,
        tenant_id: str,
        attendance_date: date,
        *,
        campus_id: str | None = None,
    ) -> list[AttendanceRecordDocument]:
        query: dict[str, object] = {"tenant_id": tenant_id, "attendance_date": attendance_date.isoformat()}
        if campus_id:
            query["campus_id"] = campus_id
        cursor = self.collection.find(query).sort("check_in_time", -1)
        return [AttendanceRecordDocument.model_validate(self.normalize_document(document)) async for document in cursor]
