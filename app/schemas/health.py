"""Schema ของ health endpoint."""

from pydantic import BaseModel

from app.core.config import AppEnv


class HealthOut(BaseModel):
    """Response ของ ``GET /health``."""

    status: str
    app: str
    env: AppEnv
