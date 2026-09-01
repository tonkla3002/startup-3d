"""Repository test — ยิง Postgres จริงตาม PROJECT_RULES 5.2b (ห้าม mock session)."""

from datetime import UTC, datetime, timedelta

from app.marketplaces.base import Platform
from app.repositories.shop_repository import ShopRepository


class TestShopRepositoryGet:
    async def test_get_returns_shop_when_exists(self, db_session, shop_factory):
        # Arrange
        await shop_factory(account_id="100392024")
        # Act
        shop = await ShopRepository(db_session).get(Platform.LAZADA, "100392024")
        # Assert
        assert shop is not None
        assert shop.account_id == "100392024"

    async def test_get_returns_none_for_unknown_account(self, db_session):
        assert await ShopRepository(db_session).get(Platform.LAZADA, "nope") is None

    async def test_get_does_not_leak_across_platforms(self, db_session, shop_factory):
        """ร้าน account_id เดียวกันคนละ platform ต้องไม่ปนกัน."""
        # Arrange
        await shop_factory(account_id="same-id", platform=Platform.LAZADA)
        # Act
        other = await ShopRepository(db_session).get(Platform.SHOPEE, "same-id")
        # Assert
        assert other is None


class TestShopRepositoryList:
    async def test_list_active_excludes_inactive(self, db_session, shop_factory):
        # Arrange
        await shop_factory(account_id="active-1", is_active=True)
        await shop_factory(account_id="inactive-1", is_active=False)
        # Act
        shops = await ShopRepository(db_session).list_active()
        # Assert
        assert [shop.account_id for shop in shops] == ["active-1"]

    async def test_list_active_filters_by_platform(self, db_session, shop_factory):
        await shop_factory(account_id="lz-1", platform=Platform.LAZADA)
        await shop_factory(account_id="sp-1", platform=Platform.SHOPEE)
        shops = await ShopRepository(db_session).list_active(Platform.SHOPEE)
        assert [shop.account_id for shop in shops] == ["sp-1"]

    async def test_list_expiring_before_returns_only_soon_expiring(
        self, db_session, shop_factory
    ):
        # Arrange
        await shop_factory(account_id="soon", expires_in=timedelta(minutes=5))
        await shop_factory(account_id="later", expires_in=timedelta(days=6))
        deadline = datetime.now(UTC) + timedelta(hours=1)
        # Act
        shops = await ShopRepository(db_session).list_expiring_before(deadline)
        # Assert
        assert [shop.account_id for shop in shops] == ["soon"]

    async def test_list_expiring_ignores_inactive_shops(self, db_session, shop_factory):
        await shop_factory(
            account_id="dead", expires_in=timedelta(minutes=1), is_active=False
        )
        deadline = datetime.now(UTC) + timedelta(hours=1)
        assert await ShopRepository(db_session).list_expiring_before(deadline) == []


class TestShopRepositoryRepr:
    async def test_repr_does_not_leak_token(self, shop_factory):
        shop = await shop_factory()
        assert "at-old" not in repr(shop)
        assert "encrypted" not in repr(shop)
