"""ตรวจ OrderRepository กับ Postgres จริง."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.marketplaces.base import Platform
from app.models.order import Order
from app.repositories.order_repository import OrderRepository


def _order(shop_id: int, external_id: str = "o-1", placed_day: int = 1) -> Order:
    return Order(
        shop_id=shop_id,
        platform=Platform.LAZADA,
        external_id=external_id,
        order_number=external_id,
        status="pending",
        total_amount=Decimal("100.00"),
        currency="THB",
        placed_at=datetime(2026, 9, placed_day, tzinfo=UTC),
    )


class TestOrderRepository:
    async def test_add_then_get(self, db_session, shop_factory):
        # Arrange
        shop = await shop_factory()
        repo = OrderRepository(db_session)
        repo.add(_order(shop.id))
        await db_session.commit()
        # Act
        found = await repo.get(shop.id, "o-1")
        # Assert
        assert found is not None
        assert found.total_amount == Decimal("100.00")

    async def test_get_returns_none_for_other_shop(self, db_session, shop_factory):
        """ออเดอร์ของร้านหนึ่งต้องไม่โผล่ในอีกร้าน."""
        # Arrange
        shop_a = await shop_factory(account_id="a")
        shop_b = await shop_factory(account_id="b")
        repo = OrderRepository(db_session)
        repo.add(_order(shop_a.id))
        await db_session.commit()
        # Act & Assert
        assert await repo.get(shop_b.id, "o-1") is None

    async def test_same_external_id_allowed_across_shops(
        self, db_session, shop_factory
    ):
        """คนละร้านมีเลขออเดอร์ซ้ำกันได้ — unique ต้องผูกกับ shop_id ด้วย."""
        shop_a = await shop_factory(account_id="a")
        shop_b = await shop_factory(account_id="b")
        repo = OrderRepository(db_session)
        repo.add(_order(shop_a.id, "same"))
        repo.add(_order(shop_b.id, "same"))
        await db_session.commit()
        assert await repo.get(shop_a.id, "same") is not None
        assert await repo.get(shop_b.id, "same") is not None

    async def test_duplicate_in_same_shop_violates_constraint(
        self, db_session, shop_factory
    ):
        shop = await shop_factory()
        repo = OrderRepository(db_session)
        repo.add(_order(shop.id, "dup"))
        await db_session.commit()
        repo.add(_order(shop.id, "dup"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_list_for_shop_sorted_newest_first(self, db_session, shop_factory):
        # Arrange
        shop = await shop_factory()
        repo = OrderRepository(db_session)
        repo.add(_order(shop.id, "old", placed_day=1))
        repo.add(_order(shop.id, "new", placed_day=9))
        await db_session.commit()
        # Act
        orders = await repo.list_for_shop(shop.id)
        # Assert
        assert [order.external_id for order in orders] == ["new", "old"]

    async def test_list_for_shop_respects_limit(self, db_session, shop_factory):
        shop = await shop_factory()
        repo = OrderRepository(db_session)
        for index in range(5):
            repo.add(_order(shop.id, f"o-{index}", placed_day=index + 1))
        await db_session.commit()
        assert len(await repo.list_for_shop(shop.id, limit=2)) == 2
