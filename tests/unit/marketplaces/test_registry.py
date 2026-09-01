"""ตรวจ registry ของ platform."""

import httpx
import pytest

from app.marketplaces.base import Platform
from app.marketplaces.lazada.client import LazadaClient
from app.marketplaces.registry import SUPPORTED_PLATFORMS, build_client


class TestRegistry:
    def test_build_client_returns_lazada_client(self):
        client = build_client(Platform.LAZADA, httpx.AsyncClient())
        assert isinstance(client, LazadaClient)

    @pytest.mark.parametrize("platform", [Platform.SHOPEE, Platform.TIKTOK])
    def test_unsupported_platform_raises_not_implemented(self, platform):
        with pytest.raises(NotImplementedError):
            build_client(platform, httpx.AsyncClient())

    def test_only_lazada_is_supported_for_now(self):
        assert {Platform.LAZADA} == SUPPORTED_PLATFORMS
