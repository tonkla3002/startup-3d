"""ตรวจ OAuthService — DB จริง + client ปลอม (ไม่มี network)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.marketplaces.base import Platform
from app.repositories.oauth_state_repository import OAuthStateRepository
from app.services.oauth_service import InvalidOAuthStateError, OAuthService


class TestStartAuthorization:
    async def test_start_authorization_persists_state(
        self, db_session, fake_client, cipher
    ):
        # Arrange
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        # Act
        url = await service.start_authorization(Platform.LAZADA)
        # Assert
        state = url.split("state=")[1]
        assert await OAuthStateRepository(db_session).get_valid(state, Platform.LAZADA)

    async def test_start_authorization_generates_unique_state_each_time(
        self, db_session, fake_client, cipher
    ):
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        first = await service.start_authorization(Platform.LAZADA)
        second = await service.start_authorization(Platform.LAZADA)
        assert first != second


class TestCompleteAuthorization:
    async def test_complete_authorization_creates_shop_with_encrypted_tokens(
        self, db_session, fake_client, cipher
    ):
        # Arrange
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        url = await service.start_authorization(Platform.LAZADA)
        state = url.split("state=")[1]
        # Act
        shop = await service.complete_authorization(Platform.LAZADA, "code-1", state)
        # Assert
        assert shop.account_id == "100392024"
        assert shop.access_token_encrypted != "at-new"
        assert cipher.decrypt(shop.access_token_encrypted) == "at-new"
        assert fake_client.exchange_calls == ["code-1"]

    async def test_complete_authorization_marks_state_consumed(
        self, db_session, fake_client, cipher
    ):
        """state ใช้ได้ครั้งเดียว — ยิงซ้ำด้วย state เดิมต้องไม่ผ่าน."""
        # Arrange
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        state = (await service.start_authorization(Platform.LAZADA)).split("state=")[1]
        await service.complete_authorization(Platform.LAZADA, "code-1", state)
        # Act & Assert
        with pytest.raises(InvalidOAuthStateError):
            await service.complete_authorization(Platform.LAZADA, "code-2", state)

    async def test_unknown_state_raises(self, db_session, fake_client, cipher):
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        with pytest.raises(InvalidOAuthStateError):
            await service.complete_authorization(Platform.LAZADA, "code", "forged")

    async def test_expired_state_raises(self, db_session, fake_client, cipher):
        # Arrange
        OAuthStateRepository(db_session).add(
            "s-expired", Platform.LAZADA, datetime.now(UTC) - timedelta(seconds=1)
        )
        await db_session.commit()
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        # Act & Assert
        with pytest.raises(InvalidOAuthStateError):
            await service.complete_authorization(Platform.LAZADA, "code", "s-expired")

    async def test_reauthorize_existing_shop_updates_tokens_without_duplicate_row(
        self, db_session, fake_client, cipher, shop_factory
    ):
        # Arrange
        await shop_factory(account_id="100392024", access_token="at-old")
        service = OAuthService(db=db_session, client=fake_client, cipher=cipher)
        state = (await service.start_authorization(Platform.LAZADA)).split("state=")[1]
        # Act
        shop = await service.complete_authorization(Platform.LAZADA, "code", state)
        # Assert
        assert cipher.decrypt(shop.access_token_encrypted) == "at-new"
        from app.repositories.shop_repository import ShopRepository

        assert len(await ShopRepository(db_session).list_active(Platform.LAZADA)) == 1
