"""ตรวจว่า secret ไม่หลุดลง log ตาม STANDARDS section 8.3."""

import logging

import pytest

from app.core.logging import RedactSecretsFilter, configure_logging, redact


class TestRedact:
    @pytest.mark.parametrize(
        "text",
        [
            "app_secret=super-secret-value",
            'access_token: "abc123xyz"',
            "refresh_token=rt-987654",
            "sign=9E177E1AE4699A12",
        ],
    )
    def test_redact_hides_sensitive_values(self, text):
        # Act
        result = redact(text)
        # Assert
        assert "***REDACTED***" in result

    def test_redact_keeps_non_sensitive_text_untouched(self):
        text = "fetched 12 orders for shop_id=210251695"
        assert redact(text) == text


class TestRedactSecretsFilter:
    def test_filter_redacts_secret_in_log_record(self, caplog):
        # Arrange
        logger = logging.getLogger("test.redaction")
        logger.addFilter(RedactSecretsFilter())
        # Act
        with caplog.at_level(logging.INFO, logger="test.redaction"):
            logger.info("calling lazada with access_token=leaked-token-123")
        # Assert
        assert "leaked-token-123" not in caplog.text
        assert "***REDACTED***" in caplog.text


class TestConfigureLogging:
    def test_configure_logging_sets_level_and_attaches_filter(self):
        # Act
        configure_logging("DEBUG")
        root = logging.getLogger()
        # Assert
        assert root.level == logging.DEBUG
        assert any(
            isinstance(f, RedactSecretsFilter)
            for handler in root.handlers
            for f in handler.filters
        )
