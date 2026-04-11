"""Application dependency container."""

from __future__ import annotations

from dataclasses import dataclass

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.rate_limiter import InMemoryRateLimitBackend, RateLimiter, RedisRateLimitBackend
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.face_embedding_repository import FaceEmbeddingRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.user_repository import UserRepository
from app.services.attendance import AttendanceService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.barcode import BarcodeService
from app.services.embedding_cache import EmbeddingCache
from app.services.enrollment import EnrollmentService
from app.services.face_engine.factory import build_face_engine
from app.services.face_matcher import FaceMatcher
from app.services.health import HealthService
from app.services.image_quality import ImageQualityService
from app.services.liveness import MockLivenessDetector
from app.services.student import StudentService


@dataclass(slots=True)
class AppContainer:
    """Aggregated application services."""

    settings: Settings
    database: AsyncIOMotorDatabase
    student_service: StudentService
    enrollment_service: EnrollmentService
    attendance_service: AttendanceService
    auth_service: AuthService
    audit_service: AuditService
    health_service: HealthService
    rate_limiter: RateLimiter

    async def close(self) -> None:
        await self.rate_limiter.close()


async def build_container(database: AsyncIOMotorDatabase, settings: Settings) -> AppContainer:
    """Create the service container for the running application."""

    student_repository = StudentRepository(database)
    face_embedding_repository = FaceEmbeddingRepository(database)
    attendance_repository = AttendanceRepository(database)
    user_repository = UserRepository(database)
    audit_repository = AuditRepository(database)

    audit_service = AuditService(audit_repository)
    barcode_service = BarcodeService(settings.student_id_regex)
    image_quality_service = ImageQualityService()
    face_matcher = FaceMatcher()
    embedding_cache = EmbeddingCache(face_embedding_repository, settings.embedding_cache_ttl_seconds)
    face_engine = build_face_engine(settings)
    liveness_detector = MockLivenessDetector()

    if settings.rate_limit_storage_url:
        try:
            rate_limiter = RateLimiter(RedisRateLimitBackend(settings.rate_limit_storage_url))
            await rate_limiter.health()
        except Exception:
            rate_limiter = RateLimiter(InMemoryRateLimitBackend())
    else:
        rate_limiter = RateLimiter(InMemoryRateLimitBackend())

    student_service = StudentService(student_repository, barcode_service, audit_service, settings)
    enrollment_service = EnrollmentService(
        student_repository,
        face_embedding_repository,
        audit_service,
        face_engine,
        image_quality_service,
        face_matcher,
        embedding_cache,
        liveness_detector,
        settings,
    )
    attendance_service = AttendanceService(
        attendance_repository,
        student_repository,
        audit_service,
        face_engine,
        image_quality_service,
        face_matcher,
        embedding_cache,
        liveness_detector,
        settings,
    )
    auth_service = AuthService(user_repository, audit_service, settings)
    health_service = HealthService(database, rate_limiter, settings)

    return AppContainer(
        settings=settings,
        database=database,
        student_service=student_service,
        enrollment_service=enrollment_service,
        attendance_service=attendance_service,
        auth_service=auth_service,
        audit_service=audit_service,
        health_service=health_service,
        rate_limiter=rate_limiter,
    )
