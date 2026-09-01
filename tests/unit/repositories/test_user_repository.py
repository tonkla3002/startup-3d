"""ตรวจ UserRepository กับ Postgres จริง."""

from app.repositories.user_repository import UserRepository


class TestUserRepository:
    async def test_get_by_email_returns_user(self, db_session, user_factory):
        await user_factory(email="a@example.com")
        found = await UserRepository(db_session).get_by_email("a@example.com")
        assert found is not None

    async def test_get_by_email_returns_none_when_missing(self, db_session):
        assert await UserRepository(db_session).get_by_email("nope@example.com") is None

    async def test_get_by_oauth_returns_linked_user(self, db_session, user_factory):
        # Arrange
        user = await user_factory(provider="google", provider_user_id="g-77")
        # Act
        found = await UserRepository(db_session).get_by_oauth("google", "g-77")
        # Assert
        assert found is not None
        assert found.id == user.id

    async def test_get_by_oauth_distinguishes_providers(self, db_session, user_factory):
        """provider_user_id เดียวกันคนละ provider ต้องไม่ปนกัน."""
        await user_factory(provider="google", provider_user_id="same-id")
        assert (
            await UserRepository(db_session).get_by_oauth("github", "same-id") is None
        )

    async def test_get_by_id_returns_user(self, db_session, user_factory):
        user = await user_factory()
        assert (await UserRepository(db_session).get(user.id)).id == user.id

    async def test_repr_does_not_leak_password_hash(self, user_factory):
        user = await user_factory()
        assert "hashed_password" not in repr(user)
