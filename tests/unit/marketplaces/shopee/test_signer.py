"""Golden test ของ Shopee signer — ค่าล็อกตายตัว ห้ามแก้ตามใจ."""

from app.marketplaces.shopee import endpoints
from app.marketplaces.shopee.signer import (
    build_base_string,
    build_common_params,
    current_timestamp_s,
    sign_request,
)

PARTNER_ID = "2001234"
PARTNER_KEY = "test-partner-key"
TIMESTAMP = "1755000000"
ACCESS_TOKEN = "at-1"
SHOP_ID = "210251695"

PUBLIC_SIGN = "14adf79fc8e08fef401446f8c8cf5d44d671efa44b11b223b5b11117b1bd7c4e"
SHOP_SIGN = "f6f60340c89e8264b21ec9154d270879430407bdb38c0886848a1bfcbf327c3d"


class TestBuildBaseString:
    def test_public_api_base_string(self):
        assert build_base_string(PARTNER_ID, endpoints.ORDER_LIST, TIMESTAMP) == (
            "2001234/api/v2/order/get_order_list1755000000"
        )

    def test_shop_api_appends_token_and_shop_id(self):
        assert (
            build_base_string(
                PARTNER_ID, endpoints.ORDER_LIST, TIMESTAMP, ACCESS_TOKEN, SHOP_ID
            )
            == "2001234/api/v2/order/get_order_list1755000000at-1210251695"
        )

    def test_token_without_shop_id_is_ignored(self):
        """base string ของ shop-level ต้องมีครบทั้งคู่ ไม่งั้นถือเป็น public."""
        assert build_base_string(
            PARTNER_ID, endpoints.ORDER_LIST, TIMESTAMP, ACCESS_TOKEN, None
        ) == build_base_string(PARTNER_ID, endpoints.ORDER_LIST, TIMESTAMP)


class TestSignRequest:
    def test_public_api_signature_matches_golden(self):
        assert (
            sign_request(PARTNER_ID, PARTNER_KEY, endpoints.ORDER_LIST, TIMESTAMP)
            == PUBLIC_SIGN
        )

    def test_shop_api_signature_matches_golden(self):
        assert (
            sign_request(
                PARTNER_ID,
                PARTNER_KEY,
                endpoints.ORDER_LIST,
                TIMESTAMP,
                ACCESS_TOKEN,
                SHOP_ID,
            )
            == SHOP_SIGN
        )

    def test_signature_is_lowercase_hex(self):
        """Shopee ใช้ hex ตัวพิมพ์เล็ก ต่างจาก Lazada ที่ใช้ตัวพิมพ์ใหญ่."""
        signature = sign_request(
            PARTNER_ID, PARTNER_KEY, endpoints.ORDER_LIST, TIMESTAMP
        )
        assert signature.islower()
        assert len(signature) == 64

    def test_public_and_shop_signatures_differ(self):
        assert PUBLIC_SIGN != SHOP_SIGN

    def test_different_path_gives_different_signature(self):
        assert (
            sign_request(PARTNER_ID, PARTNER_KEY, endpoints.TOKEN_CREATE, TIMESTAMP)
            != PUBLIC_SIGN
        )


class TestBuildCommonParams:
    def test_public_params_exclude_token_and_shop(self):
        params = build_common_params(
            PARTNER_ID, PARTNER_KEY, endpoints.TOKEN_CREATE, TIMESTAMP
        )
        assert set(params) == {"partner_id", "timestamp", "sign"}

    def test_shop_params_include_token_and_shop(self):
        params = build_common_params(
            PARTNER_ID,
            PARTNER_KEY,
            endpoints.ORDER_LIST,
            TIMESTAMP,
            ACCESS_TOKEN,
            SHOP_ID,
        )
        assert params["access_token"] == ACCESS_TOKEN
        assert params["shop_id"] == SHOP_ID
        assert params["sign"] == SHOP_SIGN


class TestTimestamp:
    def test_timestamp_is_second_not_millisecond(self):
        """กับดัก: Shopee ใช้ second (10 หลัก) ส่วน Lazada ใช้ ms (13 หลัก)."""
        assert len(current_timestamp_s()) == 10
