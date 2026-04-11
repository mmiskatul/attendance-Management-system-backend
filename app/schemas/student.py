"""Student API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.common import StudentStatus
from app.schemas.common import ORMBaseModel


class StudentRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    department: str = Field(min_length=2, max_length=128)
    batch: str = Field(min_length=1, max_length=64)
    semester: str = Field(min_length=1, max_length=32)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    barcode_value: str = Field(min_length=2, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=64)
    campus_id: str | None = Field(default=None, max_length=64)


class StudentResponse(ORMBaseModel):
    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    campus_id: str
    student_id: str
    full_name: str
    department: str
    batch: str
    semester: str
    email: EmailStr
    phone: str
    status: StudentStatus
    barcode_value: str
    face_embedding_count: int
    created_at: datetime
    updated_at: datetime
