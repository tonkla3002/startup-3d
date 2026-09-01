"""Business logic ของ OAuth flow ฝั่ง marketplace."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import StreamoraError
from app.core.security import TokenCipher
from app.marketplaces.base import MarketplaceClient, Platform, TokenBundle
from app.models.marketplace_shop import MarketplaceShop
from app.repositories.oauth_state_repository import OAuthStateRepository
from app.repositories.shop_repository import ShopRepository

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
STATE_BYTES = 32


class InvalidOAuthStateError(StreamoraError):
    """state ที่ callback ส่งกลับมาไม่ตรง หมดอายุ หรือถูกใช้ไปแล้ว."""


class OAuthService:
    """ประสาน client + repository ให้ครบ flow การ authorize ร้านค้า."""

    def __init__(
        self, db: AsyncSession, client: MarketplaceClient, cipher: TokenCipher
    ) -> None:
        self.db = db
        self.client = client
        self.cipher = cipher
        self.shops = ShopRepository(db)
        self.states = OAuthStateRepository(db)

    async def start_authorization(self, platform: Platform) -> str:
        """สร้าง state + authorize URL สำหรับให้ผู้ขายกดอนุญาต.

        Returns:
            URL ที่จะ redirect ผู้ขายไป
        """
        state = secrets.token_urlsafe(STATE_BYTES)
        self.states.add(
            state=state, platform=platform, expires_at=datetime.now(UTC) + STATE_TTL
        )
        await self.db.commit()
        logger.info("oauth started platform=%s", platform.value)
        return self.client.build_authorize_url(state)

    async def complete_authorization(
        self, platform: Platform, code: str, state: str
    ) -> MarketplaceShop:
        """ตรวจ state, แลก code เป็น token แล้วบันทึกร้าน.

        Raises:
            InvalidOAuthStateError: เมื่อ state ไม่ถูกต้อง/หมดอายุ/ถูกใช้แล้ว
        """
        record = await self.states.get_valid(state, platform)
        if record is None:
            logger.warning("oauth state ไม่ถูกต้อง platform=%s", platform.value)
            raise InvalidOAuthStateError("state ไม่ถูกต้องหรือหมดอายุแล้ว")

        bundle = await self.client.exchange_code(code)
        record.consumed_at = datetime.now(UTC)
        shop = await self._upsert_shop(platform, bundle)
        await self.db.commit()
        await self.db.refresh(shop)
        logger.info(
            "oauth completed platform=%s account_id=%s",
            platform.value,
            bundle.account_id,
        )
        return shop

    async def _upsert_shop(
        self, platform: Platform, bundle: TokenBundle
    ) -> MarketplaceShop:
        """สร้างร้านใหม่ หรืออัปเดต token ของร้านเดิม."""
        shop = await self.shops.get(platform, bundle.account_id)
        if shop is None:
            shop = MarketplaceShop(platform=platform, account_id=bundle.account_id)
            self.shops.add(shop)

        shop.access_token_encrypted = self.cipher.encrypt(bundle.access_token)
        shop.refresh_token_encrypted = self.cipher.encrypt(bundle.refresh_token)
        shop.expires_at = bundle.expires_at
        shop.refresh_expires_at = bundle.refresh_expires_at
        shop.is_active = True
        return shop
