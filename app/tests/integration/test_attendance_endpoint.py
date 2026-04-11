"""Integration-style attendance endpoint tests."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api.v1.endpoints.attendance import attendance_rate_limit
from app.db.dependencies import get_attendance_service, get_current_active_user
from app.main import create_app
from app.models.attendance import AttendanceRecordDocument
from app.models.common import AttendanceStatus, StudentStatus, UserRole
from app.models.student import StudentDocument
from app.models.user import UserDocument
from app.services.attendance import AttendanceRecognitionResult


class FakeAttendanceService:
    async def recognize(self, **kwargs) -> AttendanceRecognitionResult:
        _ = kwargs
        student = StudentDocument(
            tenant_id="tenant-a",
            campus_id="main",
            student_id="STU-001",
            full_name="Alice Student",
            department="CSE",
            batch="2024",
            semester="Spring",
            email="alice@example.edu",
            phone="0123456789",
            status=StudentStatus.ACTIVE,
            barcode_value="BAR-001",
            face_embedding_count=4,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        record = AttendanceRecordDocument(
            tenant_id="tenant-a",
            campus_id="main",
            student_id="STU-001",
            attendance_date=date(2026, 4, 11),
            check_in_time=datetime(2026, 4, 11, 8, 30, tzinfo=timezone.utc),
            device_id="terminal-1",
            confidence_score=0.94,
            attendance_status=AttendanceStatus.MARKED,
            matched_embedding_id="emb-123",
            created_at=datetime(2026, 4, 11, 8, 30, tzinfo=timezone.utc),
        )
        return AttendanceRecognitionResult(
            recognized=True,
            status=AttendanceStatus.MARKED,
            confidence_score=0.94,
            student=student,
            matched_embedding_id="emb-123",
            attendance_record=record,
            message="Attendance marked successfully.",
        )


def fake_user() -> UserDocument:
    return UserDocument(
        _id="507f1f77bcf86cd799439011",
        tenant_id="tenant-a",
        username="operator1",
        hashed_password="hashed",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
    )


def test_attendance_recognize_endpoint_returns_contract() -> None:
    app = create_app(startup_enabled=False)
    app.dependency_overrides[get_current_active_user] = fake_user
    app.dependency_overrides[get_attendance_service] = lambda: FakeAttendanceService()
    app.dependency_overrides[attendance_rate_limit] = lambda: None

    client = TestClient(app)
    response = client.post(
        "/api/v1/attendance/recognize",
        json={
            "image_base64": "a" * 60,
            "device_id": "terminal-1",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recognized"] is True
    assert payload["student"]["student_id"] == "STU-001"
    assert payload["attendance_status"] == "marked"
