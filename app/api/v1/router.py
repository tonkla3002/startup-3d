"""รวม router ของ API v1 ทั้งหมด."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, login, shops, webhooks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(login.router)
api_router.include_router(auth.router)
api_router.include_router(shops.router)
api_router.include_router(webhooks.router)
