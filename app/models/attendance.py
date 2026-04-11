"""Attendance persistence model."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import AttendanceSession, AttendanceStatus


class AttendanceRecordDocument(BaseModel):
    """MongoDB attendance record document."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    campus_id: str
    student_id: str
    attendance_date: date
    attendance_session: AttendanceSession = AttendanceSession.DAILY
    check_in_time: datetime
    device_id: str
    confidence_score: float
    attendance_status: AttendanceStatus
    matched_embedding_id: str | None = None
    created_at: datetime
