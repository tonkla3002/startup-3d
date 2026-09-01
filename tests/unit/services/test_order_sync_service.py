"""ตรวจ OrderSyncService — DB จริง + client ปลอม."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.marketplaces.errors import MarketplaceError, TokenExpiredError
from app.repositories.order_repository import OrderRepository
from app.services.order_sync_service import OrderSyncService


class TestSyncOrders:
    async def test_new_orders_are_created(
        self,
        db_session,
        cipher,
        shop_factory,
        order_client_factory,
        normalized_order_factory,
    ):
        # Arrange
        shop = await shop_factory()
        client = order_client_factory(orders=[normalized_order_factory()])
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        # Act
        result = await service.sync_orders(shop)
        # Assert
        assert result.fetched == 1
        assert result.created == 1
        assert result.updated == 0
        stored = await OrderRepository(db_session).get(shop.id, "217864843")
        assert stored is not None
        assert stored.total_amount == Decimal("1250.50")

    async def test_existing_order_is_updated_not_duplicated(
        self,
        db_session,
        cipher,
        shop_factory,
        order_client_factory,
        normalized_order_factory,
    ):
        """sync ซ้ำต้องอัปเดตของเดิม ไม่สร้างแถวใหม่."""
        # Arrange
        shop = await shop_factory()
        client = order_client_factory(orders=[normalized_order_factory()])
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        await service.sync_orders(shop)
        client._orders = [normalized_order_factory(status="shipped", total="1300.00")]
        # Act
        result = await service.sync_orders(shop)
        # Assert
        assert result.created == 0
        assert result.updated == 1
        stored = await OrderRepository(db_session).get(shop.id, "217864843")
        assert stored.status == "shipped"
        assert stored.total_amount == Decimal("1300.00")
        assert len(await OrderRepository(db_session).list_for_shop(shop.id)) == 1

    async def test_empty_result_is_handled(
        self, db_session, cipher, shop_factory, order_client_factory
    ):
        shop = await shop_factory()
        service = OrderSyncService(
            db=db_session, client=order_client_factory(orders=[]), cipher=cipher
        )
        result = await service.sync_orders(shop)
        assert (result.fetched, result.created, result.updated) == (0, 0, 0)

    async def test_default_window_is_last_seven_days(
        self,
        db_session,
        cipher,
        shop_factory,
        order_client_factory,
        normalized_order_factory,
    ):
        # Arrange
        shop = await shop_factory()
        client = order_client_factory(orders=[normalized_order_factory()])
        captured = {}

        async def fetch_orders(credentials, since, limit=100):
            captured["since"] = since
            return [normalized_order_factory()]

        client.fetch_orders = fetch_orders
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        # Act
        await service.sync_orders(shop)
        # Assert
        delta = datetime.now(UTC) - captured["since"]
        assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)

    async def test_explicit_since_is_passed_through(
        self, db_session, cipher, shop_factory, order_client_factory
    ):
        shop = await shop_factory()
        client = order_client_factory(orders=[])
        captured = {}

        async def fetch_orders(credentials, since, limit=100):
            captured["since"] = since
            return []

        client.fetch_orders = fetch_orders
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        moment = datetime(2026, 8, 1, tzinfo=UTC)
        await service.sync_orders(shop, since=moment)
        assert captured["since"] == moment


class TestTokenHandling:
    async def test_expired_token_triggers_refresh_then_retry(
        self,
        db_session,
        cipher,
        shop_factory,
        order_client_factory,
        normalized_order_factory,
    ):
        """token หมดอายุกลางคัน → refresh แล้วยิงใหม่ ต้องได้ข้อมูลครบ."""
        # Arrange
        shop = await shop_factory(expires_in=timedelta(days=5))
        client = order_client_factory(
            orders=[normalized_order_factory()],
            fail_first_with=TokenExpiredError(
                "lazada", "IllegalAccessToken", "expired"
            ),
        )
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        # Act
        result = await service.sync_orders(shop)
        # Assert
        assert result.created == 1
        assert client.fetch_calls == 2
        assert client.refresh_calls == ["rt-old"]

    async def test_business_error_propagates(
        self, db_session, cipher, shop_factory, order_client_factory
    ):
        shop = await shop_factory()
        client = order_client_factory(
            orders=[], fail_first_with=MarketplaceError("lazada", "Boom", "พัง")
        )
        service = OrderSyncService(db=db_session, client=client, cipher=cipher)
        with pytest.raises(MarketplaceError):
            await service.sync_orders(shop)
