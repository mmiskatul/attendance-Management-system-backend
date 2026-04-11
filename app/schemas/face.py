"""Face enrollment schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.student import StudentResponse


class FaceSamplePayload(BaseModel):
    image_base64: str = Field(min_length=50)
    pose: str | None = Field(default=None, max_length=32)


class FaceAnalyzeRequest(BaseModel):
    image_base64: str = Field(min_length=50)
    expected_pose: str | None = Field(default=None, max_length=32)


class FaceEnrollmentRequest(BaseModel):
    student_id: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^[A-Za-z0-9]{3}-[A-Za-z0-9]{2}-[A-Za-z0-9]{3}$",
    )
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


class FaceAnalyzeResponse(BaseModel):
    provider_name: str
    pose_reliable: bool
    faces_count: int
    primary_pose: str | None
    detection_score: float | None
    quality_score: float | None
    expected_pose: str | None
    pose_match: bool | None


class FaceEnrollmentResponse(BaseModel):
    student: StudentResponse
    enrolled_count: int
    embeddings: list[FaceEmbeddingResponse]
    rejected_samples: list[RejectedSampleResponse]
