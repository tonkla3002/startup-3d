"""แม็ป platform -> client factory.

การเพิ่ม platform ใหม่ต้องแก้แค่ไฟล์นี้กับโฟลเดอร์ของ platform นั้น
ห้ามมี ``if platform == ...`` ใน service layer
"""

from collections.abc import Callable

import httpx

from app.core.config import LazadaSettings
from app.marketplaces.base import MarketplaceClient, Platform
from app.marketplaces.lazada.client import LazadaClient


def _build_lazada(http: httpx.AsyncClient) -> MarketplaceClient:
    return LazadaClient(http=http, settings=LazadaSettings())


CLIENT_FACTORIES: dict[Platform, Callable[[httpx.AsyncClient], MarketplaceClient]] = {
    Platform.LAZADA: _build_lazada,
}

SUPPORTED_PLATFORMS = frozenset(CLIENT_FACTORIES)


def build_client(platform: Platform, http: httpx.AsyncClient) -> MarketplaceClient:
    """สร้าง client ของ platform ที่ระบุ.

    Raises:
        NotImplementedError: เมื่อยังไม่ได้ implement platform นั้น
    """
    factory = CLIENT_FACTORIES.get(platform)
    if factory is None:
        raise NotImplementedError(f"ยังไม่รองรับ platform: {platform}")
    return factory(http)
