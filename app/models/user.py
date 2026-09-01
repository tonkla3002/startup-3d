"""ผู้ใช้ระบบ Streamora (คนละเรื่องกับร้านค้าบน marketplace)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """บัญชีผู้ใช้ที่ล็อกอินเข้ามาใช้ระบบ.

    ``hashed_password`` เป็น nullable เพราะ user ที่ login ผ่าน OAuth อย่างเดียว
    ไม่มี password ตาม PROJECT_RULES section 4.2
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        """ไม่แสดง hashed_password ใน repr."""
        return (
            f"User(id={self.id!r}, email={self.email!r}, is_active={self.is_active!r})"
        )
