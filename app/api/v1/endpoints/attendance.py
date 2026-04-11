"""Attendance endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.serializers import to_attendance_record_response, to_student_response
from app.core.config import Settings, get_settings
from app.db.dependencies import build_rate_limit_dependency, get_attendance_service, get_runtime_settings, require_roles
from app.models.common import UserRole
from app.models.user import UserDocument
from app.schemas.attendance import (
    AttendanceRecognizeRequest,
    AttendanceRecognizeResponse,
    DailyAttendanceResponse,
    StudentAttendanceResponse,
)
from app.services.attendance import AttendanceService
from app.utils.time import current_local_date


settings_snapshot = get_settings()
attendance_rate_limit = build_rate_limit_dependency(
    namespace="attendance",
    limit=settings_snapshot.attendance_rate_limit_per_minute,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/recognize", response_model=AttendanceRecognizeResponse, status_code=status.HTTP_200_OK)
async def recognize_attendance(
    payload: AttendanceRecognizeRequest,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
    _: None = Depends(attendance_rate_limit),
) -> AttendanceRecognizeResponse:
    result = await attendance_service.recognize(
        image_payload=payload.image_base64,
        device_id=payload.device_id,
        actor_id=current_user.id or current_user.username,
        tenant_id=payload.tenant_id or current_user.tenant_id,
        campus_id=payload.campus_id,
        attendance_session=payload.attendance_session,
        captured_at=payload.captured_at,
    )
    return AttendanceRecognizeResponse(
        recognized=result.recognized,
        student=to_student_response(result.student) if result.student else None,
        confidence_score=result.confidence_score,
        attendance_status=result.status,
        matched_embedding_id=result.matched_embedding_id,
        attendance_record=to_attendance_record_response(result.attendance_record) if result.attendance_record else None,
        message=result.message,
    )


@router.get("/student/{student_id}", response_model=StudentAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_student_attendance(
    student_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> StudentAttendanceResponse:
    records = await attendance_service.list_student_attendance(
        tenant_id=current_user.tenant_id,
        student_id=student_id,
        skip=skip,
        limit=limit,
    )
    return StudentAttendanceResponse(
        student_id=student_id,
        records=[to_attendance_record_response(item) for item in records],
    )


@router.get("/daily", response_model=DailyAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_daily_attendance(
    attendance_date: date | None = Query(default=None),
    campus_id: str | None = Query(default=None),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
    settings: Settings = Depends(get_runtime_settings),
) -> DailyAttendanceResponse:
    resolved_date = attendance_date or current_local_date(settings.timezone)
    records = await attendance_service.list_daily_attendance(
        tenant_id=current_user.tenant_id,
        attendance_date=resolved_date,
        campus_id=campus_id,
    )
    return DailyAttendanceResponse(
        attendance_date=resolved_date,
        campus_id=campus_id,
        total_records=len(records),
        records=[to_attendance_record_response(item) for item in records],
    )
