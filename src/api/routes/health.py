from fastapi import APIRouter

from src.api.schemas import ApiResponse, HealthData
from src.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check() -> ApiResponse[HealthData]:
    return ApiResponse(
        success=True,
        data=HealthData(status="ok", app_env=settings.app_env),
    )
