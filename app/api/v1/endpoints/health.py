"""Health check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    """Liveness probe — ตอบ 200 เสมอถ้า process ยังอยู่."""
    return HealthOut(status="ok", app=settings.app_name, env=settings.app_env)
