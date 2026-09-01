"""จัดการร้านที่ผูกไว้แล้ว และสั่ง sync ออเดอร์ (ต้องล็อกอินก่อน)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import Cipher, ClientFactory, DbSession, get_current_user
from app.marketplaces.base import Platform
from app.marketplaces.errors import MarketplaceError
from app.models.marketplace_shop import MarketplaceShop
from app.repositories.order_repository import OrderRepository
from app.repositories.shop_repository import ShopRepository
from app.schemas.order import OrderListOut, OrderOut, SyncResultOut
from app.schemas.shop import ShopListOut, ShopOut
from app.services.order_sync_service import OrderSyncService

router = APIRouter(
    prefix="/shops",
    tags=["shops"],
    dependencies=[Depends(get_current_user)],  # ต้องล็อกอินก่อน
)


async def _get_shop(db: DbSession, shop_id: int) -> MarketplaceShop:
    """หาร้านจาก id.

    Raises:
        HTTPException: 404 เมื่อไม่พบร้าน
    """
    shop = await db.get(MarketplaceShop, shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ไม่พบร้านนี้"
        )
    return shop


@router.get("", response_model=ShopListOut)
async def list_shops(db: DbSession, platform: Platform | None = None) -> ShopListOut:
    """คืนรายการร้านที่ active — ไม่มี token ใน response ตาม STANDARDS 8.2."""
    shops = await ShopRepository(db).list_active(platform)
    items = [ShopOut.model_validate(shop) for shop in shops]
    return ShopListOut(items=items, total=len(items))


@router.get("/{shop_id}/orders", response_model=OrderListOut)
async def list_orders(
    shop_id: int, db: DbSession, limit: int = Query(default=100, ge=1, le=500)
) -> OrderListOut:
    """คืนออเดอร์ล่าสุดของร้านที่เก็บไว้ใน DB."""
    await _get_shop(db, shop_id)
    orders = await OrderRepository(db).list_for_shop(shop_id, limit=limit)
    items = [OrderOut.model_validate(order) for order in orders]
    return OrderListOut(items=items, total=len(items))


@router.post("/{shop_id}/sync/orders", response_model=SyncResultOut)
async def sync_orders(
    shop_id: int,
    db: DbSession,
    make_client: ClientFactory,
    cipher: Cipher,
    since: datetime | None = None,
) -> SyncResultOut:
    """สั่งดึงออเดอร์จาก marketplace เข้ามาเก็บใน DB.

    Raises:
        HTTPException: 404 เมื่อไม่พบร้าน, 502 เมื่อ marketplace ตอบ error
    """
    shop = await _get_shop(db, shop_id)
    service = OrderSyncService(db=db, client=make_client(shop.platform), cipher=cipher)
    try:
        result = await service.sync_orders(shop, since=since)
    except MarketplaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        ) from exc
    return SyncResultOut(
        fetched=result.fetched, created=result.created, updated=result.updated
    )
