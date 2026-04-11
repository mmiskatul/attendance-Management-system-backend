"""Face enrollment schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.student import StudentResponse


class FaceSamplePayload(BaseModel):
    image_base64: str = Field(min_length=50)
    pose: str | None = Field(default=None, max_length=32)


class FaceEnrollmentRequest(BaseModel):
    student_id: str = Field(min_length=2, max_length=64)
    samples: list[FaceSamplePayload] = Field(min_length=3, max_length=10)
    tenant_id: str | None = Field(default=None, max_length=64)
    campus_id: str | None = Field(default=None, max_length=64)


class FaceEmbeddingResponse(BaseModel):
    id: str | None
    pose: str | None
    quality_score: float
    model_name: str
    created_at: datetime


class RejectedSampleResponse(BaseModel):
    index: int
    reason: str


class FaceEnrollmentResponse(BaseModel):
    student: StudentResponse
    enrolled_count: int
    embeddings: list[FaceEmbeddingResponse]
    rejected_samples: list[RejectedSampleResponse]
