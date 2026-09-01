"""ตรวจ TokenService — การ refresh token."""

from datetime import UTC, datetime, timedelta

from app.services.token_service import REFRESH_MARGIN, TokenService


class TestNeedsRefresh:
    async def test_token_far_from_expiry_does_not_need_refresh(
        self, db_session, fake_client, cipher, shop_factory
    ):
        shop = await shop_factory(expires_in=timedelta(days=5))
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        assert service.needs_refresh(shop) is False

    async def test_token_inside_margin_needs_refresh(
        self, db_session, fake_client, cipher, shop_factory
    ):
        shop = await shop_factory(expires_in=REFRESH_MARGIN - timedelta(minutes=1))
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        assert service.needs_refresh(shop) is True


class TestGetCredentials:
    async def test_returns_decrypted_token_without_refresh_when_fresh(
        self, db_session, fake_client, cipher, shop_factory
    ):
        # Arrange
        shop = await shop_factory(access_token="at-old", expires_in=timedelta(days=5))
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        # Act
        credentials = await service.get_credentials(shop)
        # Assert
        assert credentials.access_token == "at-old"
        assert fake_client.refresh_calls == []

    async def test_refreshes_automatically_when_near_expiry(
        self, db_session, fake_client, cipher, shop_factory
    ):
        # Arrange
        shop = await shop_factory(
            access_token="at-old",
            refresh_token="rt-old",
            expires_in=timedelta(minutes=1),
        )
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        # Act
        credentials = await service.get_credentials(shop)
        # Assert
        assert credentials.access_token == "at-new"
        assert fake_client.refresh_calls == ["rt-old"]


class TestRefresh:
    async def test_refresh_persists_new_encrypted_tokens(
        self, db_session, fake_client, cipher, shop_factory
    ):
        # Arrange
        shop = await shop_factory(access_token="at-old", refresh_token="rt-old")
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        # Act
        updated = await service.refresh(shop)
        # Assert
        assert cipher.decrypt(updated.access_token_encrypted) == "at-new"
        assert cipher.decrypt(updated.refresh_token_encrypted) == "rt-new"
        assert updated.expires_at > datetime.now(UTC)

    async def test_refresh_expiring_only_touches_shops_near_expiry(
        self, db_session, fake_client, cipher, shop_factory
    ):
        # Arrange
        await shop_factory(account_id="soon", expires_in=timedelta(minutes=1))
        await shop_factory(account_id="later", expires_in=timedelta(days=5))
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        # Act
        refreshed = await service.refresh_expiring()
        # Assert
        assert [shop.account_id for shop in refreshed] == ["soon"]

    async def test_refresh_expiring_returns_empty_when_nothing_due(
        self, db_session, fake_client, cipher, shop_factory
    ):
        await shop_factory(expires_in=timedelta(days=5))
        service = TokenService(db=db_session, client=fake_client, cipher=cipher)
        assert await service.refresh_expiring() == []
