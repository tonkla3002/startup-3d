"""ออเดอร์ที่ sync มาจาก marketplace."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.marketplaces.base import Platform
from app.models.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    """ออเดอร์ 1 รายการของร้าน 1 ร้าน.

    ``external_id`` คือ order id ฝั่ง marketplace — unique ต่อร้าน ไม่ใช่ต่อทั้งระบบ
    เพราะคนละร้านอาจมีเลขซ้ำกันได้
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("shop_id", "external_id", name="uq_orders_shop_id"),
        Index("ix_orders_placed_at", "placed_at"),
        Index("ix_orders_shop_id_status", "shop_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_shops.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_enum", native_enum=False, length=16),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_number: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """สรุปสั้น ๆ ไม่มีข้อมูลลูกค้า."""
        return (
            f"Order(id={self.id!r}, shop_id={self.shop_id!r}, "
            f"external_id={self.external_id!r}, status={self.status!r})"
        )
