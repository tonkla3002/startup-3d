"""Endpoint ดูร้านที่ authorize เข้ามาแล้ว."""

from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.marketplaces.base import Platform
from app.repositories.shop_repository import ShopRepository
from app.schemas.shop import ShopListOut, ShopOut

router = APIRouter(
    prefix="/shops",
    tags=["shops"],
    dependencies=[Depends(get_current_user)],  # ต้องล็อกอินก่อน
)


@router.get("", response_model=ShopListOut)
async def list_shops(db: DbSession, platform: Platform | None = None) -> ShopListOut:
    """คืนรายการร้านที่ active — ไม่มี token ใน response ตาม STANDARDS 8.2."""
    shops = await ShopRepository(db).list_active(platform)
    items = [ShopOut.model_validate(shop) for shop in shops]
    return ShopListOut(items=items, total=len(items))
