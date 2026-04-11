"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.container import AppContainer
from app.core.exceptions import AuthenticationAppError, AuthorizationAppError
from app.core.security import decode_access_token
from app.models.common import UserRole
from app.models.user import UserDocument
from app.services.attendance import AttendanceService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.enrollment import EnrollmentService
from app.services.health import HealthService
from app.services.student import StudentService


bearer_scheme = HTTPBearer(auto_error=False)


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Application container is not initialized.")
    return container


def get_runtime_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


def get_auth_service(container: AppContainer = Depends(get_container)) -> AuthService:
    return container.auth_service


def get_student_service(container: AppContainer = Depends(get_container)) -> StudentService:
    return container.student_service


def get_enrollment_service(container: AppContainer = Depends(get_container)) -> EnrollmentService:
    return container.enrollment_service


def get_attendance_service(container: AppContainer = Depends(get_container)) -> AttendanceService:
    return container.attendance_service


def get_audit_service(container: AppContainer = Depends(get_container)) -> AuditService:
    return container.audit_service


def get_health_service(container: AppContainer = Depends(get_container)) -> HealthService:
    return container.health_service


async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_runtime_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserDocument:
    if credentials is None:
        raise AuthenticationAppError("Missing bearer token.")

    payload = decode_access_token(
        credentials.credentials,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return await auth_service.get_active_user(payload.sub)


def require_roles(*roles: UserRole) -> Callable[..., UserDocument]:
    async def dependency(current_user: UserDocument = Depends(get_current_active_user)) -> UserDocument:
        if current_user.role not in roles:
            raise AuthorizationAppError()
        return current_user

    return dependency


def build_rate_limit_dependency(*, namespace: str, limit: int, window_seconds: int = 60) -> Callable[..., None]:
    async def dependency(
        request: Request,
        container: AppContainer = Depends(get_container),
        current_user: UserDocument = Depends(get_current_active_user),
    ) -> None:
        client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")
        device_hint = request.headers.get("x-device-id", "unknown-device")
        key = f"{namespace}:{current_user.id or current_user.username}:{client_ip}:{device_hint}"
        await container.rate_limiter.enforce(key, limit=limit, window_seconds=window_seconds)

    return dependency
