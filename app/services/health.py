"""Health check service."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.rate_limiter import RateLimiter


class HealthService:
    """Report service health for orchestration and monitoring."""

    def __init__(self, database: AsyncIOMotorDatabase, rate_limiter: RateLimiter, settings: Settings) -> None:
        self.database = database
        self.rate_limiter = rate_limiter
        self.settings = settings

    async def check(self) -> dict[str, object]:
        db_ok = False
        try:
            await self.database.command("ping")
            db_ok = True
        except Exception:
            db_ok = False

        try:
            cache_ok = await self.rate_limiter.health()
        except Exception:
            cache_ok = False
        status = "ok" if db_ok and cache_ok else "degraded"
        return {
            "status": status,
            "service": self.settings.app_name,
            "version": self.settings.app_version,
            "checks": {
                "database": "ok" if db_ok else "failed",
                "rate_limiter": "ok" if cache_ok else "failed",
                "face_engine_provider": self.settings.face_engine_provider,
            },
        }
