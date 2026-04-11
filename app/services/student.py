"""Student service."""

from __future__ import annotations

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.exceptions import ConflictAppError, NotFoundAppError
from app.models.common import AuditAction
from app.models.student import StudentDocument
from app.repositories.student_repository import StudentRepository
from app.services.audit import AuditService
from app.services.barcode import BarcodeService
from app.utils.time import utc_now


class StudentService:
    """Manage student registration and retrieval."""

    def __init__(
        self,
        repository: StudentRepository,
        barcode_service: BarcodeService,
        audit_service: AuditService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.barcode_service = barcode_service
        self.audit_service = audit_service
        self.settings = settings

    async def register_student(
        self,
        *,
        full_name: str,
        department: str,
        batch: str,
        semester: str,
        email: str,
        phone: str,
        barcode_value: str,
        actor_id: str,
        tenant_id: str | None = None,
        campus_id: str | None = None,
    ) -> StudentDocument:
        resolved_tenant_id = tenant_id or self.settings.default_tenant_id
        resolved_campus_id = campus_id or self.settings.default_campus_id
        student_id = self.barcode_service.extract_student_id(barcode_value)
        now = utc_now()
        student = StudentDocument(
            tenant_id=resolved_tenant_id,
            campus_id=resolved_campus_id,
            student_id=student_id,
            full_name=full_name,
            department=department,
            batch=batch,
            semester=semester,
            email=email,
            phone=phone,
            barcode_value=barcode_value,
            created_at=now,
            updated_at=now,
        )
        try:
            created = await self.repository.create(student)
        except DuplicateKeyError as exc:
            raise ConflictAppError("Student or barcode already registered.") from exc

        await self.audit_service.record(
            tenant_id=resolved_tenant_id,
            campus_id=resolved_campus_id,
            actor_id=actor_id,
            action=AuditAction.STUDENT_REGISTERED.value,
            target_type="student",
            target_id=created.student_id,
            metadata={"department": created.department, "batch": created.batch},
        )
        return created

    async def get_student(self, tenant_id: str, student_id: str) -> StudentDocument:
        student = await self.repository.get_by_student_id(tenant_id, student_id)
        if student is None:
            raise NotFoundAppError("Student not found.")
        return student
