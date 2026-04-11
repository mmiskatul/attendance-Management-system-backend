"""Attendance API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.common import AttendanceSession, AttendanceStatus
from app.schemas.student import StudentResponse


class AttendanceRecognizeRequest(BaseModel):
    image_base64: str = Field(min_length=50)
    device_id: str = Field(min_length=2, max_length=128)
    tenant_id: str | None = Field(default=None, max_length=64)
    campus_id: str | None = Field(default=None, max_length=64)
    attendance_session: AttendanceSession = AttendanceSession.DAILY
    captured_at: datetime | None = None


class AttendanceRecordResponse(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    campus_id: str
    student_id: str
    attendance_date: date
    attendance_session: AttendanceSession
    check_in_time: datetime
    device_id: str
    confidence_score: float
    attendance_status: AttendanceStatus
    matched_embedding_id: str | None
    created_at: datetime


class AttendanceRecognizeResponse(BaseModel):
    recognized: bool
    student: StudentResponse | None
    confidence_score: float
    attendance_status: AttendanceStatus
    matched_embedding_id: str | None
    attendance_record: AttendanceRecordResponse | None
    message: str


class StudentAttendanceResponse(BaseModel):
    student_id: str
    records: list[AttendanceRecordResponse]


class DailyAttendanceResponse(BaseModel):
    attendance_date: date
    campus_id: str | None
    total_records: int
    records: list[AttendanceRecordResponse]
