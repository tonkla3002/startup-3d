"""ตรวจ OAuthStateRepository กับ Postgres จริง."""

from datetime import UTC, datetime, timedelta

from app.marketplaces.base import Platform
from app.repositories.oauth_state_repository import OAuthStateRepository


class TestOAuthStateRepository:
    async def test_get_valid_returns_unconsumed_state(self, db_session):
        # Arrange
        repo = OAuthStateRepository(db_session)
        repo.add("s-1", Platform.LAZADA, datetime.now(UTC) + timedelta(minutes=10))
        await db_session.commit()
        # Act
        found = await repo.get_valid("s-1", Platform.LAZADA)
        # Assert
        assert found is not None

    async def test_get_valid_returns_none_for_expired_state(self, db_session):
        repo = OAuthStateRepository(db_session)
        repo.add("s-old", Platform.LAZADA, datetime.now(UTC) - timedelta(minutes=1))
        await db_session.commit()
        assert await repo.get_valid("s-old", Platform.LAZADA) is None

    async def test_get_valid_returns_none_for_consumed_state(self, db_session):
        # Arrange
        repo = OAuthStateRepository(db_session)
        record = repo.add(
            "s-used", Platform.LAZADA, datetime.now(UTC) + timedelta(minutes=10)
        )
        record.consumed_at = datetime.now(UTC)
        await db_session.commit()
        # Act & Assert
        assert await repo.get_valid("s-used", Platform.LAZADA) is None

    async def test_get_valid_checks_platform(self, db_session):
        repo = OAuthStateRepository(db_session)
        repo.add("s-2", Platform.LAZADA, datetime.now(UTC) + timedelta(minutes=10))
        await db_session.commit()
        assert await repo.get_valid("s-2", Platform.SHOPEE) is None
