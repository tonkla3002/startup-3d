"""Declarative base พร้อม naming convention สำหรับ constraint.

naming convention จำเป็นมากสำหรับ Alembic autogenerate ให้ผลตรงกับ Postgres
ตาม PROJECT_RULES section 2.5b
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base ของทุก ORM model ในระบบ."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """เพิ่ม created_at / updated_at ให้ model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
