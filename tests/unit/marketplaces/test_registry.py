"""ตรวจ registry ของ platform."""

import httpx
import pytest

from app.marketplaces.base import Platform
from app.marketplaces.lazada.client import LazadaClient
from app.marketplaces.registry import SUPPORTED_PLATFORMS, build_client
from app.marketplaces.shopee.client import ShopeeClient


class TestRegistry:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [(Platform.LAZADA, LazadaClient), (Platform.SHOPEE, ShopeeClient)],
    )
    def test_build_client_returns_right_type(self, platform, expected):
        assert isinstance(build_client(platform, httpx.AsyncClient()), expected)

    def test_unsupported_platform_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            build_client(Platform.TIKTOK, httpx.AsyncClient())

    def test_supported_platforms(self):
        assert {Platform.LAZADA, Platform.SHOPEE} == SUPPORTED_PLATFORMS


class TestProtocolConformance:
    @pytest.mark.parametrize("platform", [Platform.LAZADA, Platform.SHOPEE])
    def test_every_client_implements_full_contract(self, platform):
        """ทุก client ต้องมีเมธอดครบตาม MarketplaceClient protocol."""
        client = build_client(platform, httpx.AsyncClient())
        for method in (
            "build_authorize_url",
            "exchange_code",
            "refresh_token",
            "fetch_orders",
            "verify_webhook",
        ):
            assert callable(getattr(client, method)), f"{platform} ขาด {method}"
        assert client.platform is platform
