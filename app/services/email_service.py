"""ส่งอีเมลแจ้งเตือนผ่าน SMTP.

ใช้ ``aiosmtplib`` เพราะ ``smtplib`` มาตรฐานเป็น blocking I/O ซึ่งห้ามเรียกตรง ๆ
ใน ``async def`` ตาม PROJECT_RULES section 2.4
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import EmailSettings
from app.core.exceptions import StreamoraError

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(StreamoraError):
    """ยังไม่ได้ตั้งค่า SMTP ครบ."""


class EmailSendError(StreamoraError):
    """ส่งอีเมลไม่สำเร็จ."""


def build_message(
    settings: EmailSettings, to: str, subject: str, body: str
) -> EmailMessage:
    """ประกอบอีเมล 1 ฉบับ.

    Args:
        settings: config ของ SMTP (ใช้เอาที่อยู่ผู้ส่ง)
        to: อีเมลผู้รับ
        subject: หัวเรื่อง
        body: เนื้อความแบบ plain text

    Returns:
        EmailMessage ที่พร้อมส่ง
    """
    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


class EmailService:
    """ห่อ aiosmtplib ไว้ให้ layer อื่นเรียกใช้โดยไม่ต้องรู้จัก SMTP."""

    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    async def send(self, to: str, subject: str, body: str) -> None:
        """ส่งอีเมล 1 ฉบับ.

        Args:
            to: อีเมลผู้รับ
            subject: หัวเรื่อง
            body: เนื้อความแบบ plain text

        Raises:
            EmailNotConfiguredError: เมื่อยังตั้งค่า SMTP ไม่ครบ
            EmailSendError: เมื่อ SMTP ปฏิเสธหรือต่อไม่ได้
        """
        if not self.settings.is_configured:
            raise EmailNotConfiguredError("ยังไม่ได้ตั้งค่า SMTP ครบ")

        message = build_message(self.settings, to=to, subject=subject, body=body)
        try:
            await aiosmtplib.send(
                message,
                hostname=self.settings.host,
                port=self.settings.port,
                username=self.settings.user,
                password=self.settings.password.get_secret_value(),
                use_tls=self.settings.use_tls,
                start_tls=self.settings.start_tls,
                timeout=self.settings.timeout_seconds,
            )
        except aiosmtplib.SMTPException as exc:
            # ห้ามใส่ password ลง log — ข้อความจาก exception บางตัวมี credential ปน
            logger.error("ส่งอีเมลไม่สำเร็จ to=%s subject=%s", to, subject)
            raise EmailSendError("ส่งอีเมลไม่สำเร็จ") from exc

        logger.info("ส่งอีเมลแล้ว to=%s subject=%s", to, subject)
