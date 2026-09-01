"""ตรวจ worker ต่ออายุ token."""

from contextlib import asynccontextmanager
from datetime import timedelta

import pytest

from app.marketplaces.base import Platform
from app.marketplaces.errors import MarketplaceError
from app.workers import token_refresh


@pytest.fixture
def session_factory(db_session):
    """คืน session ของ test เดิม เพื่อให้ rollback ครอบคลุมสิ่งที่ worker ทำ."""

    @asynccontextmanager
    async def _factory():
        yield db_session

    def _call():
        return _factory()

    return _call


@pytest.fixture(autouse=True)
def stub_build_client(monkeypatch, fake_client):
    """ให้ worker ใช้ client ปลอมแทนการยิงจริง."""
    monkeypatch.setattr(
        token_refresh, "build_client", lambda platform, http: fake_client
    )
    return fake_client


class _RecordingAlerts:
    """AlertService ปลอมที่จดว่าแจ้งเตือนอะไรไปบ้าง."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def notify_token_refresh_failed(
        self, platform: str, account_id: str, reason: str
    ) -> bool:
        self.calls.append(
            {"platform": platform, "account_id": account_id, "reason": reason}
        )
        return True


class TestRunOnce:
    async def test_refreshes_only_expiring_shops(
        self, session_factory, cipher, shop_factory, http_client
    ):
        # Arrange
        await shop_factory(account_id="soon", expires_in=timedelta(minutes=1))
        await shop_factory(account_id="later", expires_in=timedelta(days=5))
        # Act
        count = await token_refresh.run_once(
            session_factory, http_client, cipher, alerts=_RecordingAlerts()
        )
        # Assert
        assert count == 1

    async def test_returns_zero_when_nothing_due(
        self, session_factory, cipher, shop_factory, http_client
    ):
        await shop_factory(expires_in=timedelta(days=5))
        assert (
            await token_refresh.run_once(
                session_factory, http_client, cipher, alerts=_RecordingAlerts()
            )
            == 0
        )

    async def test_skips_unsupported_platform(
        self, session_factory, cipher, shop_factory, http_client
    ):
        """ร้านของ platform ที่ยังไม่ implement ต้องถูกข้าม ไม่ทำให้ทั้งรอบพัง."""
        await shop_factory(
            account_id="tt", platform=Platform.TIKTOK, expires_in=timedelta(minutes=1)
        )
        assert (
            await token_refresh.run_once(
                session_factory, http_client, cipher, alerts=_RecordingAlerts()
            )
            == 0
        )

    async def test_one_failing_shop_does_not_stop_the_rest(
        self, session_factory, cipher, shop_factory, http_client, stub_build_client
    ):
        # Arrange
        await shop_factory(account_id="bad", expires_in=timedelta(minutes=1))
        await shop_factory(account_id="good", expires_in=timedelta(minutes=2))
        calls = {"n": 0}
        original = stub_build_client.refresh_token

        async def flaky(refresh_token):
            calls["n"] += 1
            if calls["n"] == 1:
                raise MarketplaceError("lazada", "Boom", "พัง")
            return await original(refresh_token)

        stub_build_client.refresh_token = flaky
        alerts = _RecordingAlerts()
        # Act
        count = await token_refresh.run_once(
            session_factory, http_client, cipher, alerts=alerts
        )
        # Assert
        assert count == 1
        assert len(alerts.calls) == 1
        assert alerts.calls[0]["account_id"] == "bad"
        assert "Boom" in alerts.calls[0]["reason"]


class TestRunForever:
    async def test_loops_until_cancelled(
        self, session_factory, cipher, http_client, monkeypatch
    ):
        # Arrange
        rounds = {"n": 0}

        async def counting_run_once(*args, **kwargs):
            rounds["n"] += 1
            return 0

        async def fast_sleep(_seconds):
            if rounds["n"] >= 3:
                raise asyncio.CancelledError

        import asyncio

        monkeypatch.setattr(token_refresh, "run_once", counting_run_once)
        # Act
        with pytest.raises(asyncio.CancelledError):
            await token_refresh.run_forever(
                session_factory, http_client, cipher, sleep=fast_sleep
            )
        # Assert
        assert rounds["n"] == 3

    async def test_error_in_one_round_does_not_break_loop(
        self, session_factory, cipher, http_client, monkeypatch
    ):
        import asyncio

        rounds = {"n": 0}

        async def exploding_run_once(*args, **kwargs):
            rounds["n"] += 1
            raise RuntimeError("boom")

        async def fast_sleep(_seconds):
            if rounds["n"] >= 2:
                raise asyncio.CancelledError

        monkeypatch.setattr(token_refresh, "run_once", exploding_run_once)
        with pytest.raises(asyncio.CancelledError):
            await token_refresh.run_forever(
                session_factory, http_client, cipher, sleep=fast_sleep
            )
        assert rounds["n"] == 2
