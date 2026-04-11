"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.common import UserRole
from app.schemas.common import ORMBaseModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    tenant_id: str | None = Field(default=None, max_length=64)


class AuthenticatedUserResponse(ORMBaseModel):
    id: str | None = Field(default=None, alias="_id")
    tenant_id: str
    username: str
    role: UserRole
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUserResponse
