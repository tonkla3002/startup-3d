"""Model กลางที่ normalize แล้ว — ใช้ร่วมกันทุก platform.

service layer เห็นเฉพาะ model ในไฟล์นี้ ไม่เห็น payload ดิบของ marketplace ใด
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.marketplaces.base import Platform


class NormalizedOrder(BaseModel):
    """ออเดอร์ที่แปลงเป็นรูปแบบกลางของระบบแล้ว."""

    model_config = ConfigDict(frozen=True)

    platform: Platform
    account_id: str
    order_id: str
    order_number: str | None = None
    status: str
    total_amount: Decimal
    currency: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
