"""ร้านค้าที่ authorize เข้ามาแล้ว พร้อม token ที่เข้ารหัสไว้."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.marketplaces.base import Platform
from app.models.base import Base, TimestampMixin


class MarketplaceShop(Base, TimestampMixin):
    """ร้านหนึ่งร้านบน marketplace หนึ่งเจ้า.

    token ถูกเก็บแบบ **เข้ารหัส** (ไม่ใช่ hash) เพราะต้องถอดกลับมาใช้ยิง API
    ตาม PROJECT_RULES section 8 / STANDARDS section 8.2
    """

    __tablename__ = "marketplace_shops"
    __table_args__ = (
        UniqueConstraint(
            "platform", "account_id", name="uq_marketplace_shops_platform"
        ),
        Index("ix_marketplace_shops_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_enum", native_enum=False, length=16),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    shop_name: Mapped[str | None] = mapped_column(String(255))

    access_token_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    refresh_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        """ปิดบัง token ไม่ให้หลุดผ่าน repr/log."""
        return (
            f"MarketplaceShop(id={self.id!r}, platform={self.platform!r}, "
            f"account_id={self.account_id!r}, is_active={self.is_active!r})"
        )
