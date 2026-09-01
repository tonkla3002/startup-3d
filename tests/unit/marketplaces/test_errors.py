"""ตรวจ error hierarchy ของ marketplace layer."""

import pytest

from app.core.exceptions import StreamoraError
from app.marketplaces.errors import (
    MarketplaceError,
    MarketplaceUnavailableError,
    RateLimitError,
    TokenExpiredError,
)


class TestMarketplaceError:
    def test_error_message_includes_platform_and_code(self):
        error = MarketplaceError("lazada", "IllegalAccessToken", "token invalid")
        assert str(error) == "[lazada] IllegalAccessToken: token invalid"

    @pytest.mark.parametrize(
        "error_class", [RateLimitError, TokenExpiredError, MarketplaceUnavailableError]
    )
    def test_subclasses_are_catchable_as_marketplace_error(self, error_class):
        """service layer ต้องจับ MarketplaceError ตัวเดียวแล้วครอบคลุมทุกกรณีได้."""
        error = error_class("lazada", "code", "message")
        assert isinstance(error, MarketplaceError)
        assert isinstance(error, StreamoraError)
