"""Application configuration."""

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "University Attendance Management API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    docs_enabled: bool = True
    timezone: str = "UTC"
    request_id_header: str = "X-Request-ID"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "attendance_management"
    mongo_max_pool_size: int = 100
    mongo_min_pool_size: int = 10

    jwt_secret_key: SecretStr = SecretStr("change-this-secret-before-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    default_tenant_id: str = "university-main"
    default_campus_id: str = "main-campus"
    student_id_regex: str = r"(?P<student_id>[A-Za-z0-9_-]{4,32})$"

    face_engine_provider: str = "mock"
    face_model_name: str = "buffalo_l"
    face_match_threshold: float = 0.78
    duplicate_face_threshold: float = 0.88
    min_face_quality_score: float = 0.60
    min_attendance_quality_score: float = 0.55
    min_enrollment_samples: int = 3
    max_enrollment_samples: int = 10
    embedding_cache_ttl_seconds: int = 300
    liveness_enabled: bool = False

    rate_limit_storage_url: str | None = None
    attendance_rate_limit_per_minute: int = 60
    admin_rate_limit_per_minute: int = 30

    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: SecretStr | None = None
    bootstrap_admin_role: str = "admin"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return []

    @property
    def docs_url(self) -> str | None:
        return "/docs" if self.docs_enabled else None

    @property
    def redoc_url(self) -> str | None:
        return "/redoc" if self.docs_enabled else None

    @property
    def openapi_url(self) -> str | None:
        return f"{self.api_v1_prefix}/openapi.json" if self.docs_enabled else None

    @property
    def jwt_secret(self) -> str:
        return self.jwt_secret_key.get_secret_value()

    @property
    def bootstrap_admin_secret(self) -> str | None:
        if self.bootstrap_admin_password is None:
            return None
        return self.bootstrap_admin_password.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
