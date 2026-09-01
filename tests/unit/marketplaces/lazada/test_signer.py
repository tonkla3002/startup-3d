"""Golden test ของ Lazada signer.

ค่า signature ในไฟล์นี้คำนวณไว้ครั้งเดียวแล้ว **ล็อกตายตัว** ถ้ามีใครแก้ลำดับ sort,
encoding, ตัวพิมพ์ของ hex หรือหน่วยของ timestamp ทีหลัง test ชุดนี้จะพังทันที
ห้ามแก้ค่าคาดหวังเพื่อให้ test ผ่าน โดยไม่ยืนยันกับ docs ทางการก่อน
"""

import pytest

from app.marketplaces.lazada import endpoints
from app.marketplaces.lazada.signer import (
    build_base_string,
    build_signed_params,
    current_timestamp_ms,
    sign_request,
)

ORDERS_PARAMS = {
    "app_key": "141659",
    "timestamp": "1755000000000",
    "sign_method": "sha256",
    "access_token": "dummy-token",
}
EXPECTED_ORDERS_SIGN = (
    "9E177E1AE4699A126153B5B106EEA0813FB6E26F4670A42F85ACB6EE8002ECDB"
)


class TestBuildBaseString:
    def test_build_base_string_concatenates_path_then_sorted_pairs(self):
        # Arrange / Act
        base = build_base_string(endpoints.ORDERS_GET, ORDERS_PARAMS)
        # Assert
        assert base == (
            "/orders/get"
            "access_tokendummy-token"
            "app_key141659"
            "sign_methodsha256"
            "timestamp1755000000000"
        )

    def test_build_base_string_excludes_sign_key(self):
        # Arrange
        params = {**ORDERS_PARAMS, "sign": "STALE_VALUE"}
        # Act
        base = build_base_string(endpoints.ORDERS_GET, params)
        # Assert
        assert "STALE_VALUE" not in base


class TestSignRequest:
    def test_sign_request_with_known_params_returns_expected_signature(
        self, app_secret
    ):
        # Arrange / Act
        signature = sign_request(endpoints.ORDERS_GET, ORDERS_PARAMS, app_secret)
        # Assert
        assert signature == EXPECTED_ORDERS_SIGN

    def test_sign_request_returns_uppercase_hex(self, app_secret):
        """Lazada ใช้ hex ตัวพิมพ์ใหญ่ ต่างจาก Shopee ที่ใช้ตัวพิมพ์เล็ก."""
        signature = sign_request(endpoints.ORDERS_GET, ORDERS_PARAMS, app_secret)
        assert signature.isupper()
        assert len(signature) == 64
        assert all(char in "0123456789ABCDEF" for char in signature)

    def test_sign_request_ignores_stale_sign_key_if_present(self, app_secret):
        # Arrange
        with_stale = {**ORDERS_PARAMS, "sign": "STALE_VALUE"}
        # Act / Assert
        assert sign_request(endpoints.ORDERS_GET, with_stale, app_secret) == (
            sign_request(endpoints.ORDERS_GET, ORDERS_PARAMS, app_secret)
        )

    def test_sign_request_is_order_independent(self, app_secret):
        """key ต้องถูก sort ก่อน concat — สลับลำดับ dict แล้วผลต้องเท่าเดิม."""
        forward = {"a": "1", "b": "2", "c": "3"}
        reverse = {"c": "3", "b": "2", "a": "1"}
        assert sign_request("/x", forward, app_secret) == sign_request(
            "/x", reverse, app_secret
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("timestamp", "1755000000001"),
            ("app_key", "999999"),
            ("access_token", "other-token"),
        ],
    )
    def test_sign_request_changes_when_any_param_changes(
        self, app_secret, field, value
    ):
        # Arrange
        mutated = {**ORDERS_PARAMS, field: value}
        # Act / Assert
        assert sign_request(endpoints.ORDERS_GET, mutated, app_secret) != (
            EXPECTED_ORDERS_SIGN
        )

    def test_sign_request_changes_when_api_path_changes(self, app_secret):
        """base string ขึ้นต้นด้วย api_path — คนละ endpoint ต้องได้คนละ sign."""
        assert sign_request(endpoints.PRODUCTS_GET, ORDERS_PARAMS, app_secret) != (
            EXPECTED_ORDERS_SIGN
        )

    def test_sign_request_with_wrong_secret_returns_different_signature(self):
        assert sign_request(endpoints.ORDERS_GET, ORDERS_PARAMS, "wrong") != (
            EXPECTED_ORDERS_SIGN
        )


class TestBuildSignedParams:
    def test_build_signed_params_includes_all_common_params(
        self, app_key, app_secret, timestamp_ms
    ):
        # Act
        params = build_signed_params(
            api_path=endpoints.ORDERS_GET,
            app_key=app_key,
            app_secret=app_secret,
            timestamp=timestamp_ms,
            access_token="dummy-token",
        )
        # Assert
        assert params == {**ORDERS_PARAMS, "sign": EXPECTED_ORDERS_SIGN}

    def test_build_signed_params_with_extra_params_returns_expected_signature(
        self, app_key, app_secret, timestamp_ms
    ):
        # Act
        params = build_signed_params(
            api_path=endpoints.ORDERS_GET,
            app_key=app_key,
            app_secret=app_secret,
            timestamp=timestamp_ms,
            access_token="dummy-token",
            extra={"created_after": "2026-09-01T00:00:00+07:00"},
        )
        # Assert
        assert params["created_after"] == "2026-09-01T00:00:00+07:00"
        assert params["sign"] == (
            "53F12F5805C73EAD32273B48D213D5071C4C55781B53C7411CAA3D948DDB0637"
        )

    def test_build_signed_params_omits_access_token_for_public_api(
        self, app_key, app_secret, timestamp_ms
    ):
        """API แลก token ยังไม่มี access_token — ต้องไม่แนบ key นี้เข้าไป."""
        # Act
        params = build_signed_params(
            api_path=endpoints.TOKEN_CREATE,
            app_key=app_key,
            app_secret=app_secret,
            timestamp=timestamp_ms,
            extra={"code": "auth-code-abc"},
        )
        # Assert
        assert "access_token" not in params
        assert params["sign"] == (
            "DDC61488A46D50A8ECB9B6478147E7AE671F22D1B0AA834D78BA4657F0006356"
        )

    def test_build_signed_params_sign_matches_standalone_signer(
        self, app_key, app_secret, timestamp_ms
    ):
        params = build_signed_params(
            api_path=endpoints.ORDERS_GET,
            app_key=app_key,
            app_secret=app_secret,
            timestamp=timestamp_ms,
            access_token="dummy-token",
        )
        recomputed = sign_request(endpoints.ORDERS_GET, params, app_secret)
        assert params["sign"] == recomputed


class TestCurrentTimestampMs:
    def test_current_timestamp_ms_is_millisecond_not_second(self):
        """กับดักคลาสสิก: Lazada ใช้ ms ส่วน Shopee ใช้ s — ยาว 13 หลักคือ ms."""
        assert len(current_timestamp_ms()) == 13
        assert current_timestamp_ms().isdigit()
