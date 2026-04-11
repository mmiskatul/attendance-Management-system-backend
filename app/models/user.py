"""User persistence model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import UserRole


class UserDocument(BaseModel):
    """MongoDB user document."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    username: str
    hashed_password: str
    role: UserRole
    is_active: bool = True
    created_at: datetime
