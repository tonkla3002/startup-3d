"""Data access ของ oauth_states."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.marketplaces.base import Platform
from app.models.oauth_state import OAuthState


class OAuthStateRepository:
    """Query ที่เกี่ยวกับ OAuth state ทั้งหมดอยู่ที่นี่."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, state: str, platform: Platform, expires_at: datetime) -> OAuthState:
        """เพิ่ม state ใหม่เข้า session (ยังไม่ commit — commit ที่ service)."""
        record = OAuthState(state=state, platform=platform, expires_at=expires_at)
        self.db.add(record)
        return record

    async def get_valid(
        self, state: str, platform: Platform, now: datetime | None = None
    ) -> OAuthState | None:
        """คืน state ที่ยังไม่หมดอายุและยังไม่เคยถูกใช้."""
        reference = now or datetime.now(UTC)
        result = await self.db.execute(
            select(OAuthState).where(
                OAuthState.state == state,
                OAuthState.platform == platform,
                OAuthState.consumed_at.is_(None),
                OAuthState.expires_at > reference,
            )
        )
        return result.scalar_one_or_none()
