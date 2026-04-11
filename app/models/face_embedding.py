"""Face embedding persistence model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FaceEmbeddingDocument(BaseModel):
    """MongoDB face embedding document."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    campus_id: str
    student_id: str
    embedding_binary: bytes
    embedding_dim: int
    pose: str | None = None
    quality_score: float
    model_name: str
    is_active: bool = True
    created_at: datetime
