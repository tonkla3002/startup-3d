"""State ของ OAuth flow — ใช้กัน CSRF ตอน callback."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.marketplaces.base import Platform
from app.models.base import Base, TimestampMixin


class OAuthState(Base, TimestampMixin):
    """ค่า state ที่สุ่มตอนเริ่ม authorize และต้องเจอกลับตอน callback."""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_enum", native_enum=False, length=16),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
