"""Health endpoints."""

from fastapi import APIRouter, Depends, status

from app.db.dependencies import get_health_service
from app.schemas.health import HealthResponse
from app.services.health import HealthService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check(health_service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return HealthResponse.model_validate(await health_service.check())
