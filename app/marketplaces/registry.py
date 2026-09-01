"""แม็ป platform -> client factory.

การเพิ่ม platform ใหม่ต้องแก้แค่ไฟล์นี้กับโฟลเดอร์ของ platform นั้น
ห้ามมี ``if platform == ...`` ใน service layer
"""

from collections.abc import Callable

import httpx

from app.core.config import LazadaSettings, ShopeeSettings
from app.marketplaces.base import MarketplaceClient, Platform
from app.marketplaces.lazada.client import LazadaClient
from app.marketplaces.shopee.client import ShopeeClient


def _build_lazada(http: httpx.AsyncClient) -> MarketplaceClient:
    return LazadaClient(http=http, settings=LazadaSettings())


def _build_shopee(http: httpx.AsyncClient) -> MarketplaceClient:
    return ShopeeClient(http=http, settings=ShopeeSettings())


CLIENT_FACTORIES: dict[Platform, Callable[[httpx.AsyncClient], MarketplaceClient]] = {
    Platform.LAZADA: _build_lazada,
    Platform.SHOPEE: _build_shopee,
}

SUPPORTED_PLATFORMS = frozenset(CLIENT_FACTORIES)

SETTINGS_FACTORIES: dict[Platform, Callable[[], object]] = {
    Platform.LAZADA: LazadaSettings,
    Platform.SHOPEE: ShopeeSettings,
}


def is_configured(platform: Platform) -> bool:
    """True เมื่อ platform นั้นตั้ง credential ครบแล้ว.

    กันไม่ให้ redirect ผู้ขายไปหน้า authorize ด้วย app_key ว่าง ซึ่งจะได้ error
    หน้าตาไม่รู้เรื่องจากฝั่ง marketplace แทนที่จะบอกตรง ๆ ว่ายังไม่ได้ตั้งค่า
    """
    build_settings = SETTINGS_FACTORIES.get(platform)
    if build_settings is None:
        return False
    return bool(getattr(build_settings(), "is_configured", False))


def build_client(platform: Platform, http: httpx.AsyncClient) -> MarketplaceClient:
    """สร้าง client ของ platform ที่ระบุ.

    Raises:
        NotImplementedError: เมื่อยังไม่ได้ implement platform นั้น
    """
    factory = CLIENT_FACTORIES.get(platform)
    if factory is None:
        raise NotImplementedError(f"ยังไม่รองรับ platform: {platform}")
    return factory(http)
