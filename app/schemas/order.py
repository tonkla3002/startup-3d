"""Schema ของออเดอร์."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.marketplaces.base import Platform


class OrderOut(BaseModel):
    """ออเดอร์ที่ตอบออกไปทาง API ของเรา."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    platform: Platform
    external_id: str
    order_number: str | None = None
    status: str
    total_amount: Decimal
    currency: str
    placed_at: datetime | None = None


class OrderListOut(BaseModel):
    """Response wrapper ตาม STANDARDS section 3."""

    items: list[OrderOut]
    total: int


class SyncResultOut(BaseModel):
    """สรุปผลการ sync."""

    fetched: int
    created: int
    updated: int
