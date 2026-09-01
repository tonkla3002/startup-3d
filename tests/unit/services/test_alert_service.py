"""ตรวจ AlertService — การแจ้งเตือนต้องไม่ทำให้งานหลักพัง."""

from app.core.config import EmailSettings, Settings
from app.services.alert_service import AlertService
from app.services.email_service import EmailSendError


class _RecordingEmail:
    """EmailService ปลอมที่จดว่าถูกเรียกด้วยอะไร."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[dict[str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append({"to": to, "subject": subject, "body": body})


class TestRecipient:
    def test_uses_alert_email_to_when_set(self, email_settings):
        settings = Settings(alert_email_to="ops@example.com", _env_file=None)
        service = AlertService(settings, email_settings, _RecordingEmail())
        assert service.recipient == "ops@example.com"

    def test_falls_back_to_smtp_sender(self, email_settings):
        settings = Settings(alert_email_to="", _env_file=None)
        service = AlertService(settings, email_settings, _RecordingEmail())
        assert service.recipient == email_settings.sender


class TestIsEnabled:
    def test_enabled_when_smtp_configured(self, email_settings):
        service = AlertService(
            Settings(_env_file=None), email_settings, _RecordingEmail()
        )
        assert service.is_enabled is True

    def test_disabled_without_smtp(self):
        service = AlertService(
            Settings(_env_file=None), EmailSettings(_env_file=None), _RecordingEmail()
        )
        assert service.is_enabled is False


class TestNotifyTokenRefreshFailed:
    async def test_sends_email_with_context(self, email_settings):
        # Arrange
        email = _RecordingEmail()
        service = AlertService(Settings(_env_file=None), email_settings, email)
        # Act
        sent = await service.notify_token_refresh_failed(
            platform="lazada",
            account_id="100392024",
            reason="IllegalAccessToken: หมดอายุ",
        )
        # Assert
        assert sent is True
        message = email.sent[0]
        assert "lazada" in message["subject"]
        assert "100392024" in message["body"]
        assert "IllegalAccessToken" in message["body"]

    async def test_skipped_when_email_not_configured(self):
        # Arrange
        email = _RecordingEmail()
        service = AlertService(
            Settings(_env_file=None), EmailSettings(_env_file=None), email
        )
        # Act & Assert
        assert await service.notify_token_refresh_failed("lazada", "1", "x") is False
        assert email.sent == []

    async def test_send_failure_does_not_raise(self, email_settings):
        """ส่งแจ้งเตือนไม่ได้ ต้องไม่ทำให้ผู้เรียกพังตาม."""
        email = _RecordingEmail(error=EmailSendError("smtp ล่ม"))
        service = AlertService(Settings(_env_file=None), email_settings, email)
        assert await service.notify_token_refresh_failed("lazada", "1", "x") is False

    async def test_body_does_not_contain_tokens(self, email_settings):
        email = _RecordingEmail()
        service = AlertService(Settings(_env_file=None), email_settings, email)
        await service.notify_token_refresh_failed("lazada", "100392024", "boom")
        body = email.sent[0]["body"].lower()
        assert "access_token" not in body
        assert "refresh_token" not in body or "refresh token" in body
