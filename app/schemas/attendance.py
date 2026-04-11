"""Attendance API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

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


class AttendanceStreamConfigureMessage(BaseModel):
    type: Literal["configure"]
    device_id: str = Field(min_length=2, max_length=128)
    campus_id: str | None = Field(default=None, max_length=64)
    attendance_session: AttendanceSession = AttendanceSession.DAILY


class AttendanceStreamFrameMessage(BaseModel):
    type: Literal["frame"]
    image_base64: str = Field(min_length=50)
    captured_at: datetime | None = None


class AttendanceStreamPingMessage(BaseModel):
    type: Literal["ping"]


class AttendanceStreamStopMessage(BaseModel):
    type: Literal["stop"]


class AttendanceStreamEvent(BaseModel):
    event: str
    message: str
    device_id: str | None = None
    campus_id: str | None = None
    recognized: bool | None = None
    confidence_score: float | None = None
    attendance_status: AttendanceStatus | None = None
    matched_embedding_id: str | None = None
    student: StudentResponse | None = None
    attendance_record: AttendanceRecordResponse | None = None
    cooldown_seconds: int | None = None
