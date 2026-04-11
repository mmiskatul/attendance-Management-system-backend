"""Attendance recognition and query service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.exceptions import NotFoundAppError
from app.models.attendance import AttendanceRecordDocument
from app.models.common import AttendanceSession, AttendanceStatus, AuditAction
from app.models.student import StudentDocument
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.student_repository import StudentRepository
from app.services.audit import AuditService
from app.services.embedding_cache import EmbeddingCache
from app.services.face_engine.base import FaceEngine
from app.services.face_matcher import FaceMatcher
from app.services.image_quality import ImageQualityService
from app.services.liveness import LivenessDetector
from app.utils.images import crop_image, decode_base64_image, ensure_minimum_size
from app.utils.pagination import sanitize_pagination
from app.utils.time import current_local_date, utc_now


@dataclass(slots=True)
class AttendanceRecognitionResult:
    recognized: bool
    status: AttendanceStatus
    confidence_score: float
    student: StudentDocument | None
    matched_embedding_id: str | None
    attendance_record: AttendanceRecordDocument | None
    message: str


class AttendanceService:
    """Recognize live faces and manage attendance records."""

    def __init__(
        self,
        repository: AttendanceRepository,
        student_repository: StudentRepository,
        audit_service: AuditService,
        face_engine: FaceEngine,
        image_quality_service: ImageQualityService,
        face_matcher: FaceMatcher,
        embedding_cache: EmbeddingCache,
        liveness_detector: LivenessDetector,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.student_repository = student_repository
        self.audit_service = audit_service
        self.face_engine = face_engine
        self.image_quality_service = image_quality_service
        self.face_matcher = face_matcher
        self.embedding_cache = embedding_cache
        self.liveness_detector = liveness_detector
        self.settings = settings

    async def recognize(
        self,
        *,
        image_payload: str,
        device_id: str,
        actor_id: str,
        tenant_id: str,
        campus_id: str | None = None,
        attendance_session: AttendanceSession = AttendanceSession.DAILY,
        captured_at: datetime | None = None,
    ) -> AttendanceRecognitionResult:
        resolved_campus_id = campus_id or self.settings.default_campus_id
        attendance_date = captured_at.date() if captured_at else current_local_date(self.settings.timezone)
        image = decode_base64_image(image_payload)
        ensure_minimum_size(image)

        faces = await self.face_engine.detect(image)
        if len(faces) != 1:
            return await self._reject(
                tenant_id=tenant_id,
                campus_id=resolved_campus_id,
                actor_id=actor_id,
                target_id=device_id,
                reason="Exactly one live face must be present for attendance recognition.",
            )

        face = faces[0]
        crop = crop_image(image, face.bbox)
        quality = self.image_quality_service.assess(crop, min_score=self.settings.min_attendance_quality_score)
        if not quality.is_acceptable:
            reason = ", ".join(quality.reasons) if quality.reasons else "low_quality"
            return await self._reject(
                tenant_id=tenant_id,
                campus_id=resolved_campus_id,
                actor_id=actor_id,
                target_id=device_id,
                reason=f"Attendance quality check failed: {reason}",
            )

        if self.settings.liveness_enabled:
            liveness = await self.liveness_detector.assess(crop)
            if not liveness.passed:
                return await self._reject(
                    tenant_id=tenant_id,
                    campus_id=resolved_campus_id,
                    actor_id=actor_id,
                    target_id=device_id,
                    reason="Liveness verification failed.",
                )

        embedding = await self.face_engine.embed(image, face)
        gallery = await self.embedding_cache.get_scope_embeddings(tenant_id, resolved_campus_id)
        match = self.face_matcher.find_best_match(embedding.vector, gallery)
        if match is None or match.confidence < self.settings.face_match_threshold:
            await self.audit_service.record(
                tenant_id=tenant_id,
                campus_id=resolved_campus_id,
                actor_id=actor_id,
                action=AuditAction.ATTENDANCE_REJECTED.value,
                target_type="attendance",
                target_id=device_id,
                metadata={"reason": "unknown_face", "confidence": match.confidence if match else None},
            )
            return AttendanceRecognitionResult(
                recognized=False,
                status=AttendanceStatus.UNKNOWN,
                confidence_score=match.confidence if match else 0.0,
                student=None,
                matched_embedding_id=match.embedding_id if match else None,
                attendance_record=None,
                message="Face not recognized with sufficient confidence.",
            )

        student = await self.student_repository.get_by_student_id(tenant_id, match.student_id)
        if student is None:
            raise NotFoundAppError("Matched student record was not found.")

        existing = await self.repository.get_by_student_and_date(
            tenant_id=tenant_id,
            student_id=student.student_id,
            attendance_date=attendance_date,
            attendance_session=attendance_session,
        )
        if existing is not None:
            await self.audit_service.record(
                tenant_id=tenant_id,
                campus_id=resolved_campus_id,
                actor_id=actor_id,
                action=AuditAction.ATTENDANCE_DUPLICATE.value,
                target_type="attendance",
                target_id=existing.id or student.student_id,
                metadata={"student_id": student.student_id, "device_id": device_id},
            )
            return AttendanceRecognitionResult(
                recognized=True,
                status=AttendanceStatus.DUPLICATE,
                confidence_score=match.confidence,
                student=student,
                matched_embedding_id=match.embedding_id,
                attendance_record=existing,
                message="Attendance already marked for this student today.",
            )

        now = captured_at or utc_now()
        record = AttendanceRecordDocument(
            tenant_id=tenant_id,
            campus_id=resolved_campus_id,
            student_id=student.student_id,
            attendance_date=attendance_date,
            attendance_session=attendance_session,
            check_in_time=now,
            device_id=device_id,
            confidence_score=match.confidence,
            attendance_status=AttendanceStatus.MARKED,
            matched_embedding_id=match.embedding_id,
            created_at=utc_now(),
        )
        try:
            stored = await self.repository.create(record)
        except DuplicateKeyError:
            stored = await self.repository.get_by_student_and_date(
                tenant_id=tenant_id,
                student_id=student.student_id,
                attendance_date=attendance_date,
                attendance_session=attendance_session,
            )

        await self.audit_service.record(
            tenant_id=tenant_id,
            campus_id=resolved_campus_id,
            actor_id=actor_id,
            action=AuditAction.ATTENDANCE_MARKED.value,
            target_type="attendance",
            target_id=stored.id if stored else student.student_id,
            metadata={"student_id": student.student_id, "device_id": device_id, "confidence": match.confidence},
        )

        return AttendanceRecognitionResult(
            recognized=True,
            status=AttendanceStatus.MARKED,
            confidence_score=match.confidence,
            student=student,
            matched_embedding_id=match.embedding_id,
            attendance_record=stored,
            message="Attendance marked successfully.",
        )

    async def list_student_attendance(
        self,
        *,
        tenant_id: str,
        student_id: str,
        skip: int,
        limit: int,
    ) -> list[AttendanceRecordDocument]:
        safe_skip, safe_limit = sanitize_pagination(skip=skip, limit=limit)
        return await self.repository.list_by_student(tenant_id, student_id, skip=safe_skip, limit=safe_limit)

    async def list_daily_attendance(
        self,
        *,
        tenant_id: str,
        attendance_date: date,
        campus_id: str | None = None,
    ) -> list[AttendanceRecordDocument]:
        return await self.repository.list_by_day(tenant_id, attendance_date, campus_id=campus_id)

    async def _reject(
        self,
        *,
        tenant_id: str,
        campus_id: str,
        actor_id: str,
        target_id: str,
        reason: str,
    ) -> AttendanceRecognitionResult:
        await self.audit_service.record(
            tenant_id=tenant_id,
            campus_id=campus_id,
            actor_id=actor_id,
            action=AuditAction.ATTENDANCE_REJECTED.value,
            target_type="attendance",
            target_id=target_id,
            metadata={"reason": reason},
        )
        return AttendanceRecognitionResult(
            recognized=False,
            status=AttendanceStatus.REJECTED,
            confidence_score=0.0,
            student=None,
            matched_embedding_id=None,
            attendance_record=None,
            message=reason,
        )
