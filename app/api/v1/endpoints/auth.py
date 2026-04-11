"""Authentication endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.v1.serializers import to_authenticated_user_response
from app.core.config import Settings
from app.db.dependencies import get_auth_service, get_runtime_settings
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_runtime_settings),
) -> TokenResponse:
    token, user = await auth_service.login(
        username=payload.username,
        password=payload.password,
        tenant_id=payload.tenant_id,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=to_authenticated_user_response(user),
    )
