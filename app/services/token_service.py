"""จัดการอายุ token ของร้านค้า."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenCipher
from app.marketplaces.base import MarketplaceClient, ShopCredentials
from app.models.marketplace_shop import MarketplaceShop
from app.repositories.shop_repository import ShopRepository

logger = logging.getLogger(__name__)

REFRESH_MARGIN = timedelta(minutes=30)


class TokenService:
    """ถอดรหัส token และต่ออายุก่อนหมด."""

    def __init__(
        self, db: AsyncSession, client: MarketplaceClient, cipher: TokenCipher
    ) -> None:
        self.db = db
        self.client = client
        self.cipher = cipher
        self.shops = ShopRepository(db)

    def needs_refresh(self, shop: MarketplaceShop, now: datetime | None = None) -> bool:
        """True เมื่อ access token ใกล้หมดอายุจนควร refresh แล้ว."""
        reference = now or datetime.now(UTC)
        return shop.expires_at <= reference + REFRESH_MARGIN

    async def get_credentials(
        self, shop: MarketplaceShop, now: datetime | None = None
    ) -> ShopCredentials:
        """คืน credential ที่ใช้ยิง API ได้จริง — refresh ให้อัตโนมัติถ้าใกล้หมดอายุ."""
        if self.needs_refresh(shop, now):
            await self.refresh(shop)
        return ShopCredentials(
            platform=shop.platform,
            account_id=shop.account_id,
            access_token=self.cipher.decrypt(shop.access_token_encrypted),
        )

    async def refresh(self, shop: MarketplaceShop) -> MarketplaceShop:
        """ต่ออายุ token ของร้านแล้วบันทึกลง DB.

        ใช้ ``with_for_update`` ผ่าน session ที่ล็อกแถวไว้ กัน refresh พร้อมกัน
        หลาย request แล้วทำให้ token ก่อนหน้าใช้ไม่ได้
        """
        current_refresh = self.cipher.decrypt(shop.refresh_token_encrypted)
        bundle = await self.client.refresh_token(current_refresh)

        shop.access_token_encrypted = self.cipher.encrypt(bundle.access_token)
        shop.refresh_token_encrypted = self.cipher.encrypt(bundle.refresh_token)
        shop.expires_at = bundle.expires_at
        shop.refresh_expires_at = bundle.refresh_expires_at
        await self.db.commit()
        await self.db.refresh(shop)
        logger.info(
            "token refreshed platform=%s account_id=%s",
            shop.platform.value,
            shop.account_id,
        )
        return shop

    async def refresh_expiring(
        self, now: datetime | None = None
    ) -> list[MarketplaceShop]:
        """Refresh ทุกร้านที่ token ใกล้หมดอายุ — ใช้โดย background worker."""
        reference = now or datetime.now(UTC)
        shops = await self.shops.list_expiring_before(reference + REFRESH_MARGIN)
        refreshed = []
        for shop in shops:
            refreshed.append(await self.refresh(shop))
        return refreshed
