"""ดึงออเดอร์จาก marketplace แล้วเก็บลง DB."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenCipher
from app.marketplaces.base import MarketplaceClient
from app.marketplaces.errors import TokenExpiredError
from app.marketplaces.schemas import NormalizedOrder
from app.models.marketplace_shop import MarketplaceShop
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK = timedelta(days=7)
DEFAULT_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class SyncResult:
    """สรุปผลการ sync 1 รอบ.

    Attributes:
        fetched: จำนวนออเดอร์ที่ดึงมาได้
        created: จำนวนที่เพิ่งบันทึกใหม่
        updated: จำนวนที่มีอยู่แล้วและถูกอัปเดต
    """

    fetched: int
    created: int
    updated: int


class OrderSyncService:
    """ประสาน token + client + repository ให้ครบรอบการ sync ออเดอร์."""

    def __init__(
        self, db: AsyncSession, client: MarketplaceClient, cipher: TokenCipher
    ) -> None:
        self.db = db
        self.client = client
        self.cipher = cipher
        self.orders = OrderRepository(db)
        self.tokens = TokenService(db=db, client=client, cipher=cipher)

    async def sync_orders(
        self,
        shop: MarketplaceShop,
        since: datetime | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> SyncResult:
        """ดึงออเดอร์ของร้านแล้ว upsert ลง DB.

        ถ้า token หมดอายุระหว่างทางจะ refresh แล้วลองใหม่อีก 1 ครั้ง
        ตามนโยบายใน STANDARDS section 2.6

        Args:
            shop: ร้านที่จะ sync
            since: ดึงออเดอร์ที่สร้างหลังเวลานี้ (ไม่ระบุ = ย้อนหลัง 7 วัน)
            limit: จำนวนสูงสุดต่อรอบ

        Returns:
            สรุปจำนวนที่ดึงมา/สร้างใหม่/อัปเดต
        """
        window_start = since or datetime.now(UTC) - DEFAULT_LOOKBACK
        fetched = await self._fetch_with_retry(shop, window_start, limit)

        created = 0
        updated = 0
        for item in fetched:
            if await self._upsert(shop, item):
                created += 1
            else:
                updated += 1

        await self.db.commit()
        logger.info(
            "sync เสร็จ platform=%s account_id=%s fetched=%d created=%d updated=%d",
            shop.platform.value,
            shop.account_id,
            len(fetched),
            created,
            updated,
        )
        return SyncResult(fetched=len(fetched), created=created, updated=updated)

    async def _fetch_with_retry(
        self, shop: MarketplaceShop, since: datetime, limit: int
    ) -> list[NormalizedOrder]:
        """ดึงออเดอร์ — ถ้าเจอ token หมดอายุให้ refresh แล้วลองใหม่ 1 ครั้ง."""
        credentials = await self.tokens.get_credentials(shop)
        try:
            return await self.client.fetch_orders(credentials, since=since, limit=limit)
        except TokenExpiredError:
            logger.info("token หมดอายุระหว่าง sync — refresh แล้วลองใหม่")
            await self.tokens.refresh(shop)
            credentials = await self.tokens.get_credentials(shop)
            return await self.client.fetch_orders(credentials, since=since, limit=limit)

    async def _upsert(self, shop: MarketplaceShop, item: NormalizedOrder) -> bool:
        """บันทึกออเดอร์ คืน True ถ้าเป็นการสร้างใหม่."""
        existing = await self.orders.get(shop.id, item.order_id)
        if existing is None:
            self.orders.add(
                Order(
                    shop_id=shop.id,
                    platform=item.platform,
                    external_id=item.order_id,
                    order_number=item.order_number,
                    status=item.status,
                    total_amount=item.total_amount,
                    currency=item.currency,
                    placed_at=item.created_at,
                    remote_updated_at=item.updated_at,
                )
            )
            return True

        existing.status = item.status
        existing.total_amount = item.total_amount
        existing.currency = item.currency
        existing.remote_updated_at = item.updated_at
        if item.order_number:
            existing.order_number = item.order_number
        return False
