"""Data access ของ marketplace_shops."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.marketplaces.base import Platform
from app.models.marketplace_shop import MarketplaceShop


class ShopRepository:
    """Query ที่เกี่ยวกับร้านค้าทั้งหมดอยู่ที่นี่."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, platform: Platform, account_id: str) -> MarketplaceShop | None:
        """หาร้านจาก platform + account_id.

        ทุก query ต้องมีทั้งสอง key เสมอ กัน cross-tenant leak
        """
        result = await self.db.execute(
            select(MarketplaceShop).where(
                MarketplaceShop.platform == platform,
                MarketplaceShop.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_active(
        self, platform: Platform | None = None
    ) -> list[MarketplaceShop]:
        """คืนร้านที่ยัง active ทั้งหมด (กรองตาม platform ได้)."""
        statement = select(MarketplaceShop).where(MarketplaceShop.is_active.is_(True))
        if platform is not None:
            statement = statement.where(MarketplaceShop.platform == platform)
        result = await self.db.execute(statement.order_by(MarketplaceShop.id))
        return list(result.scalars().all())

    async def list_expiring_before(self, deadline: datetime) -> list[MarketplaceShop]:
        """คืนร้านที่ access token จะหมดอายุก่อนเวลาที่กำหนด (ให้ worker refresh)."""
        result = await self.db.execute(
            select(MarketplaceShop)
            .where(
                MarketplaceShop.is_active.is_(True),
                MarketplaceShop.expires_at <= deadline,
            )
            .order_by(MarketplaceShop.expires_at)
        )
        return list(result.scalars().all())

    def add(self, shop: MarketplaceShop) -> MarketplaceShop:
        """เพิ่มร้านใหม่เข้า session (commit ที่ service)."""
        self.db.add(shop)
        return shop
