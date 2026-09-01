"""แจ้งเตือนทีมงานเมื่อระบบมีปัญหาที่ต้องมีคนเข้ามาดู.

การแจ้งเตือน **ต้องไม่ทำให้งานหลักพัง** — ถ้าส่งอีเมลไม่ได้ให้ log แล้วไปต่อ
ไม่ใช่ปล่อย exception ขึ้นไปทำให้ worker หยุด
"""

import logging

from app.core.config import EmailSettings, Settings
from app.services.email_service import EmailSendError, EmailService

logger = logging.getLogger(__name__)


class AlertService:
    """ส่งอีเมลแจ้งเตือนแบบ best-effort."""

    def __init__(
        self,
        settings: Settings,
        email_settings: EmailSettings,
        email: EmailService | None = None,
    ) -> None:
        self.settings = settings
        self.email_settings = email_settings
        self.email = email or EmailService(email_settings)

    @property
    def recipient(self) -> str:
        """ผู้รับการแจ้งเตือน — ไม่ตั้ง ALERT_EMAIL_TO ให้ใช้ SMTP_FROM แทน."""
        return self.settings.alert_email_to or self.email_settings.sender

    @property
    def is_enabled(self) -> bool:
        """True เมื่อตั้งค่า SMTP ครบและมีผู้รับ."""
        return self.email_settings.is_configured and bool(self.recipient)

    async def notify_token_refresh_failed(
        self, platform: str, account_id: str, reason: str
    ) -> bool:
        """แจ้งเตือนเมื่อ refresh token ของร้านไม่สำเร็จ.

        เคสนี้อันตรายเงียบ ๆ — ถ้าปล่อยไว้จน refresh_token หมดอายุ (30 วัน)
        ผู้ขายต้องมา authorize ใหม่ทั้งหมด

        Returns:
            True เมื่อส่งสำเร็จ, False เมื่อปิดอยู่หรือส่งไม่ได้
        """
        return await self._send(
            subject=f"[Streamora] refresh token ไม่สำเร็จ — {platform}",
            body=(
                "refresh token ของร้านนี้ไม่สำเร็จ\n\n"
                f"platform   : {platform}\n"
                f"account_id : {account_id}\n"
                f"สาเหตุ      : {reason}\n"
                f"environment: {self.settings.app_env.value}\n\n"
                "ถ้าปล่อยไว้จน refresh token หมดอายุ ผู้ขายต้อง authorize ใหม่\n"
            ),
        )

    async def _send(self, subject: str, body: str) -> bool:
        """ส่งอีเมลแบบ best-effort — ไม่ raise ออกไปข้างนอก."""
        if not self.is_enabled:
            logger.debug("ข้ามการแจ้งเตือน: ยังไม่ได้ตั้งค่าอีเมล")
            return False
        try:
            await self.email.send(to=self.recipient, subject=subject, body=body)
        except EmailSendError:
            logger.warning("ส่งอีเมลแจ้งเตือนไม่สำเร็จ subject=%s", subject)
            return False
        return True
