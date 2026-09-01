"""Schema ของร้านค้า — **ห้ามมี token อยู่ใน response ใด ๆ**."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.marketplaces.base import Platform


class ShopOut(BaseModel):
    """ข้อมูลร้านที่ตอบออกไปทาง API ของเรา."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    account_id: str
    shop_name: str | None = None
    expires_at: datetime
    refresh_expires_at: datetime
    is_active: bool


class ShopListOut(BaseModel):
    """Response wrapper แบบมาตรฐานตาม STANDARDS section 3."""

    items: list[ShopOut]
    total: int
