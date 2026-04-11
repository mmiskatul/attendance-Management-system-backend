"""Mapping helpers from domain models to API schemas."""

from __future__ import annotations

from app.models.attendance import AttendanceRecordDocument
from app.models.audit import AuditLogDocument
from app.models.face_embedding import FaceEmbeddingDocument
from app.models.student import StudentDocument
from app.models.user import UserDocument
from app.schemas.attendance import AttendanceRecordResponse
from app.schemas.audit import AuditLogResponse
from app.schemas.auth import AuthenticatedUserResponse
from app.schemas.face import FaceEmbeddingResponse
from app.schemas.student import StudentResponse


def to_student_response(student: StudentDocument) -> StudentResponse:
    return StudentResponse.model_validate(student.model_dump(by_alias=True))


def to_face_embedding_response(embedding: FaceEmbeddingDocument) -> FaceEmbeddingResponse:
    return FaceEmbeddingResponse(
        id=embedding.id,
        pose=embedding.pose,
        quality_score=embedding.quality_score,
        model_name=embedding.model_name,
        created_at=embedding.created_at,
    )


def to_attendance_record_response(record: AttendanceRecordDocument) -> AttendanceRecordResponse:
    return AttendanceRecordResponse.model_validate(record.model_dump(by_alias=True))


def to_audit_log_response(log: AuditLogDocument) -> AuditLogResponse:
    return AuditLogResponse.model_validate(log.model_dump(by_alias=True))


def to_authenticated_user_response(user: UserDocument) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse.model_validate(user.model_dump(by_alias=True))
