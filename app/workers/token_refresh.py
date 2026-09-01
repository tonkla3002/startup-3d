"""Worker ต่ออายุ token ของร้านก่อนหมดอายุ.

แยกเป็น ``run_once`` เพื่อให้ test ได้โดยไม่ต้องรอ loop จริง ส่วน ``run_forever``
เป็นแค่ตัวห่อที่เรียก ``run_once`` ซ้ำตามรอบเวลา
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_email_settings, get_settings
from app.core.security import TokenCipher
from app.marketplaces.base import Platform
from app.marketplaces.errors import MarketplaceError
from app.marketplaces.registry import SUPPORTED_PLATFORMS, build_client
from app.models.marketplace_shop import MarketplaceShop
from app.repositories.shop_repository import ShopRepository
from app.services.alert_service import AlertService
from app.services.token_service import REFRESH_MARGIN, TokenService

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 600


async def run_once(
    session_factory: async_sessionmaker,
    http: httpx.AsyncClient,
    cipher: TokenCipher,
    platforms: frozenset[Platform] = SUPPORTED_PLATFORMS,
    alerts: AlertService | None = None,
) -> int:
    """Refresh ทุกร้านที่ token ใกล้หมดอายุ 1 รอบ.

    ร้านที่ refresh ไม่ผ่านจะถูก log แล้วข้ามไป ไม่ทำให้ร้านอื่นพังตาม

    Returns:
        จำนวนร้านที่ refresh สำเร็จ
    """
    notifier = alerts or AlertService(get_settings(), get_email_settings())
    refreshed = 0
    async with session_factory() as db:
        deadline = datetime.now(UTC) + REFRESH_MARGIN
        shops = await ShopRepository(db).list_expiring_before(deadline)

        # เก็บข้อมูลที่ต้องใช้ไว้ก่อน เพราะ rollback ระหว่างทางจะ expire ORM object
        # แล้วการแตะ attribute ทีหลังจะกลายเป็น lazy load กลาง loop
        targets = [(shop.id, shop.platform, shop.account_id) for shop in shops]

        for shop_id, platform, account_id in targets:
            if platform not in platforms:
                logger.warning("ข้ามร้าน platform=%s เพราะยังไม่รองรับ", platform.value)
                continue

            shop = await db.get(MarketplaceShop, shop_id)
            if shop is None:
                continue

            service = TokenService(
                db=db, client=build_client(platform, http), cipher=cipher
            )
            try:
                await service.refresh(shop)
            except MarketplaceError as error:
                logger.exception(
                    "refresh ไม่สำเร็จ platform=%s account_id=%s",
                    platform.value,
                    account_id,
                )
                await db.rollback()
                await notifier.notify_token_refresh_failed(
                    platform=platform.value,
                    account_id=account_id,
                    reason=f"{error.code}: {error.message}",
                )
                continue
            refreshed += 1

    if refreshed:
        logger.info("refresh token สำเร็จ %d ร้าน", refreshed)
    return refreshed


async def run_forever(
    session_factory: async_sessionmaker,
    http: httpx.AsyncClient,
    cipher: TokenCipher,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> None:
    """วนเรียก ``run_once`` ตามรอบเวลาจนกว่าจะถูก cancel."""
    pause = sleep or asyncio.sleep
    while True:
        try:
            await run_once(session_factory, http, cipher)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("token refresh worker พังในรอบนี้ — จะลองใหม่รอบหน้า")
        await pause(interval_seconds)
