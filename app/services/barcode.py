"""Barcode parsing service."""

from __future__ import annotations

import re

from app.core.exceptions import ValidationAppError


class BarcodeService:
    """Extract student identifiers from scanned barcode or QR values."""

    def __init__(self, student_id_pattern: str) -> None:
        self.student_id_pattern = re.compile(student_id_pattern)

    def extract_student_id(self, barcode_value: str) -> str:
        value = barcode_value.strip()
        if not value:
            raise ValidationAppError("Barcode value is required.")

        match = self.student_id_pattern.search(value)
        if not match:
            raise ValidationAppError("Barcode value does not contain a valid student ID.")

        return match.groupdict().get("student_id", match.group(0))
