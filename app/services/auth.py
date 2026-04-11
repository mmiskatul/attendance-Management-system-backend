"""Authentication service."""

from __future__ import annotations

from datetime import timedelta

from app.core.config import Settings
from app.core.exceptions import AuthenticationAppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.common import AuditAction, UserRole
from app.models.user import UserDocument
from app.repositories.user_repository import UserRepository
from app.services.audit import AuditService
from app.utils.time import utc_now


class AuthService:
    """Authenticate and manage admin/operator users."""

    def __init__(self, repository: UserRepository, audit_service: AuditService, settings: Settings) -> None:
        self.repository = repository
        self.audit_service = audit_service
        self.settings = settings

    async def login(self, *, username: str, password: str, tenant_id: str | None = None) -> tuple[str, UserDocument]:
        resolved_tenant_id = tenant_id or self.settings.default_tenant_id
        user = await self.repository.get_by_username(resolved_tenant_id, username)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise AuthenticationAppError("Invalid username or password.")

        token = create_access_token(
            subject=user.id or user.username,
            username=user.username,
            role=user.role.value,
            tenant_id=user.tenant_id,
            secret_key=self.settings.jwt_secret,
            algorithm=self.settings.jwt_algorithm,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )
        await self.audit_service.record(
            tenant_id=user.tenant_id,
            campus_id=None,
            actor_id=user.id or user.username,
            action=AuditAction.LOGIN.value,
            target_type="user",
            target_id=user.id or user.username,
            metadata={"username": user.username, "role": user.role.value},
        )
        return token, user

    async def get_active_user(self, user_id: str) -> UserDocument:
        user = await self.repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationAppError("User account is not active.")
        return user

    async def ensure_bootstrap_admin(self) -> None:
        username = self.settings.bootstrap_admin_username
        password = self.settings.bootstrap_admin_secret
        if not username or not password:
            return

        existing_user = await self.repository.get_by_username(self.settings.default_tenant_id, username)
        if existing_user is not None:
            return

        user = UserDocument(
            tenant_id=self.settings.default_tenant_id,
            username=username,
            hashed_password=hash_password(password),
            role=UserRole(self.settings.bootstrap_admin_role),
            is_active=True,
            created_at=utc_now(),
        )
        await self.repository.create(user)
