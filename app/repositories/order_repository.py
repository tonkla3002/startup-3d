"""Data access ของ orders."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


class OrderRepository:
    """Query ที่เกี่ยวกับออเดอร์ทั้งหมดอยู่ที่นี่."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, shop_id: int, external_id: str) -> Order | None:
        """หาออเดอร์จากร้าน + เลขออเดอร์ฝั่ง marketplace."""
        result = await self.db.execute(
            select(Order).where(
                Order.shop_id == shop_id, Order.external_id == external_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_shop(self, shop_id: int, limit: int = 100) -> list[Order]:
        """คืนออเดอร์ล่าสุดของร้าน."""
        result = await self.db.execute(
            select(Order)
            .where(Order.shop_id == shop_id)
            .order_by(Order.placed_at.desc().nulls_last(), Order.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def add(self, order: Order) -> Order:
        """เพิ่มออเดอร์ใหม่เข้า session (commit ที่ service)."""
        self.db.add(order)
        return order
