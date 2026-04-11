"""Student persistence model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import StudentStatus


class StudentDocument(BaseModel):
    """MongoDB student document."""

    model_config = ConfigDict(populate_by_name=True)

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
    status: StudentStatus = StudentStatus.ACTIVE
    barcode_value: str
    face_embedding_count: int = 0
    created_at: datetime
    updated_at: datetime
