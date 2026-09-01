"""ตรวจ rate limiting (PROJECT_RULES section 8)."""

import pytest
from fastapi import HTTPException

from app.core.rate_limit import RateLimit, SlidingWindowLimiter


class TestSlidingWindowLimiter:
    def test_allows_up_to_limit(self):
        limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
        assert [limiter.check("ip", now=0) for _ in range(3)] == [True, True, True]

    def test_blocks_after_limit(self):
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60)
        limiter.check("ip", now=0)
        limiter.check("ip", now=1)
        assert limiter.check("ip", now=2) is False

    def test_window_slides_and_frees_quota(self):
        # Arrange
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=10)
        assert limiter.check("ip", now=0) is True
        assert limiter.check("ip", now=5) is False
        # Act & Assert — พ้นหน้าต่างแล้วต้องยิงได้อีก
        assert limiter.check("ip", now=10) is True

    def test_keys_are_isolated(self):
        """คนละ IP ต้องไม่กินโควตากัน."""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
        assert limiter.check("ip-a", now=0) is True
        assert limiter.check("ip-b", now=0) is True

    def test_reset_clears_counters(self):
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
        limiter.check("ip", now=0)
        limiter.reset()
        assert limiter.check("ip", now=0) is True


class _FakeRequest:
    def __init__(self, host: str = "1.2.3.4", path: str = "/api/v1/auth/google/login"):
        self.client = type("C", (), {"host": host})()
        self.url = type("U", (), {"path": path})()


class TestRateLimitDependency:
    async def test_passes_within_quota(self):
        guard = RateLimit(max_requests=2, window_seconds=60)
        await guard(_FakeRequest())
        await guard(_FakeRequest())

    async def test_raises_429_over_quota(self):
        # Arrange
        guard = RateLimit(max_requests=1, window_seconds=60)
        await guard(_FakeRequest())
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await guard(_FakeRequest())
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers["Retry-After"] == "60"

    async def test_different_paths_have_separate_quota(self):
        guard = RateLimit(max_requests=1, window_seconds=60)
        await guard(_FakeRequest(path="/a"))
        await guard(_FakeRequest(path="/b"))

    async def test_missing_client_does_not_crash(self):
        guard = RateLimit(max_requests=1, window_seconds=60)
        request = _FakeRequest()
        request.client = None
        await guard(request)
