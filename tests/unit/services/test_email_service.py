"""ตรวจ EmailService — mock aiosmtplib ทั้งหมด ไม่ส่งอีเมลจริงออกไปหาใคร."""

import aiosmtplib
import pytest

from app.core.config import EmailSettings
from app.services.email_service import (
    EmailNotConfiguredError,
    EmailSendError,
    EmailService,
    build_message,
)


class TestEmailSettings:
    def test_not_configured_when_empty(self):
        assert EmailSettings(_env_file=None).is_configured is False

    def test_configured_when_credentials_present(self, email_settings):
        assert email_settings.is_configured is True

    def test_missing_password_is_not_configured(self):
        settings = EmailSettings(
            host="smtp.test.local", user="a@example.com", password="", _env_file=None
        )
        assert settings.is_configured is False

    def test_sender_falls_back_to_user(self):
        settings = EmailSettings(
            host="smtp.test.local",
            user="fallback@example.com",
            password="x",
            from_address="",
            _env_file=None,
        )
        assert settings.sender == "fallback@example.com"

    def test_password_is_not_exposed_in_repr(self, email_settings):
        assert "test-app-password" not in repr(email_settings)


class TestBuildMessage:
    def test_message_has_headers_and_body(self, email_settings):
        # Act
        message = build_message(
            email_settings, to="ops@example.com", subject="แจ้งเตือน", body="เนื้อความ"
        )
        # Assert
        assert message["From"] == "sender@example.com"
        assert message["To"] == "ops@example.com"
        assert message["Subject"] == "แจ้งเตือน"
        assert "เนื้อความ" in message.get_content()

    def test_thai_subject_survives_encoding(self, email_settings):
        message = build_message(email_settings, "a@example.com", "หัวข้อไทย", "ทดสอบ")
        assert message["Subject"] == "หัวข้อไทย"


class TestSend:
    async def test_send_calls_smtp_with_settings(self, email_settings, mocker):
        # Arrange
        send = mocker.patch("aiosmtplib.send", return_value=({}, "ok"))
        service = EmailService(email_settings)
        # Act
        await service.send("ops@example.com", "หัวข้อ", "เนื้อความ")
        # Assert
        kwargs = send.call_args.kwargs
        assert kwargs["hostname"] == "smtp.test.local"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "sender@example.com"
        assert kwargs["start_tls"] is True

    async def test_send_passes_plain_password_only_to_smtp(
        self, email_settings, mocker
    ):
        """password ต้องถูกถอดจาก SecretStr ตอนส่งให้ SMTP เท่านั้น."""
        send = mocker.patch("aiosmtplib.send", return_value=({}, "ok"))
        await EmailService(email_settings).send("a@example.com", "s", "b")
        assert send.call_args.kwargs["password"] == "test-app-password"

    async def test_send_without_config_raises(self, mocker):
        # Arrange
        send = mocker.patch("aiosmtplib.send")
        service = EmailService(EmailSettings(_env_file=None))
        # Act & Assert
        with pytest.raises(EmailNotConfiguredError):
            await service.send("a@example.com", "s", "b")
        send.assert_not_called()

    async def test_smtp_error_becomes_email_send_error(self, email_settings, mocker):
        mocker.patch(
            "aiosmtplib.send",
            side_effect=aiosmtplib.SMTPAuthenticationError(535, "auth failed"),
        )
        with pytest.raises(EmailSendError):
            await EmailService(email_settings).send("a@example.com", "s", "b")

    async def test_connect_error_becomes_email_send_error(self, email_settings, mocker):
        mocker.patch(
            "aiosmtplib.send", side_effect=aiosmtplib.SMTPConnectError("ต่อไม่ได้")
        )
        with pytest.raises(EmailSendError):
            await EmailService(email_settings).send("a@example.com", "s", "b")

    async def test_password_never_reaches_logs(self, email_settings, mocker, caplog):
        """กฎเหล็ก section 8.3 — credential ห้ามโผล่ใน log ไม่ว่ากรณีไหน."""
        # Arrange
        mocker.patch(
            "aiosmtplib.send",
            side_effect=aiosmtplib.SMTPAuthenticationError(
                535, "auth failed for test-app-password"
            ),
        )
        # Act
        with caplog.at_level("ERROR"), pytest.raises(EmailSendError):
            await EmailService(email_settings).send("a@example.com", "s", "b")
        # Assert
        assert "test-app-password" not in caplog.text
