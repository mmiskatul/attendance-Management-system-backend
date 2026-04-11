"""Tests for barcode parsing."""

from app.services.barcode import BarcodeService


def test_barcode_service_extracts_student_id() -> None:
    service = BarcodeService(r"STU-(?P<student_id>\d{4})$")
    assert service.extract_student_id("UNIVERSITY|STU-1234") == "1234"
