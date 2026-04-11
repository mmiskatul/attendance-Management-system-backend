"""Administrative endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.serializers import to_audit_log_response
from app.db.dependencies import get_audit_service, require_roles
from app.models.common import AuditAction, UserRole
from app.models.user import UserDocument
from app.schemas.audit import AuditLogListResponse
from app.schemas.common import PaginationMeta
from app.services.audit import AuditService


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=AuditLogListResponse, status_code=status.HTTP_200_OK)
async def list_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN)),
) -> AuditLogListResponse:
    logs = await audit_service.list_logs(current_user.tenant_id, skip=skip, limit=limit)
    await audit_service.record(
        tenant_id=current_user.tenant_id,
        campus_id=None,
        actor_id=current_user.id or current_user.username,
        action=AuditAction.AUDIT_VIEWED.value,
        target_type="audit",
        target_id=current_user.id or current_user.username,
        metadata={"skip": skip, "limit": limit},
    )
    return AuditLogListResponse(
        items=[to_audit_log_response(item) for item in logs],
        pagination=PaginationMeta(skip=skip, limit=limit, returned=len(logs)),
    )
