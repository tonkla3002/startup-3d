"""Contract กลางของทุก marketplace client.

Service layer ต้องเขียนโค้ดกับ Protocol นี้เท่านั้น ห้ามอ้างถึง client ของ platform
ใดโดยตรง และห้ามมี `if platform == ...` ตาม STANDARDS section 1.2
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Platform(StrEnum):
    """Marketplace ที่ระบบรองรับ."""

    LAZADA = "lazada"
    SHOPEE = "shopee"
    TIKTOK = "tiktok"


@dataclass(frozen=True, slots=True)
class TokenBundle:
    """ชุด token ที่ได้จาก OAuth ของ marketplace.

    Attributes:
        access_token: token สำหรับเรียก API
        refresh_token: token สำหรับต่ออายุ
        expires_at: เวลาหมดอายุของ access_token (คำนวณจาก expires_in ที่ตอบมาจริง)
        refresh_expires_at: เวลาหมดอายุของ refresh_token
        account_id: ตัวระบุร้าน/บัญชีฝั่ง marketplace
    """

    access_token: str
    refresh_token: str
    expires_at: datetime
    refresh_expires_at: datetime
    account_id: str

    def __repr__(self) -> str:
        """ปิดบัง token ไม่ให้หลุดผ่าน repr/log ตาม STANDARDS section 8.3."""
        return (
            f"TokenBundle(account_id={self.account_id!r}, "
            f"expires_at={self.expires_at!r}, access_token='***')"
        )


@dataclass(frozen=True, slots=True)
class ShopCredentials:
    """Credential ของร้านหนึ่งร้านที่ service ส่งให้ client ใช้ยิง API.

    Client ห้ามอ่าน token จาก DB เอง — ต้องรับผ่าน object นี้เท่านั้น
    """

    platform: Platform
    account_id: str
    access_token: str


class MarketplaceClient(Protocol):
    """Interface ที่ทุก platform client ต้อง implement ให้ครบ."""

    platform: Platform

    def build_authorize_url(self, state: str) -> str:
        """สร้าง URL ให้ผู้ขายกดอนุญาตสิทธิ์ (OAuth step 1)."""
        ...

    async def exchange_code(self, code: str) -> TokenBundle:
        """แลก authorization code เป็น token (OAuth step 2)."""
        ...

    async def refresh_token(self, refresh_token: str) -> TokenBundle:
        """ต่ออายุ access token ด้วย refresh token."""
        ...
