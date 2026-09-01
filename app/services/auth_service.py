"""Business logic ของการ login เข้าระบบ Streamora."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SecuritySettings
from app.core.exceptions import StreamoraError
from app.core.security import create_access_token
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UnverifiedEmailError(StreamoraError):
    """Provider ไม่ยืนยันอีเมล หรือไม่ส่งอีเมลกลับมา."""


class InactiveUserError(StreamoraError):
    """User ถูกปิดใช้งาน."""


class AuthService:
    """ผูก identity จาก provider เข้ากับ user ของเราแล้วออก JWT."""

    def __init__(self, db: AsyncSession, settings: SecuritySettings) -> None:
        self.db = db
        self.settings = settings
        self.users = UserRepository(db)

    async def login_or_create_user(
        self,
        provider: str,
        provider_user_id: str,
        email: str | None,
        email_verified: bool,
        full_name: str | None = None,
    ) -> User:
        """หา user เดิมจาก identity หรือสร้างใหม่ถ้ายังไม่มี.

        Callback ต้อง idempotent — login ซ้ำด้วย provider + provider_user_id เดิม
        ต้อง map กลับ user เดิมเสมอ ตาม PROJECT_RULES section 4.5

        Raises:
            UnverifiedEmailError: เมื่อไม่มีอีเมล หรือ provider ยังไม่ยืนยันอีเมล
            InactiveUserError: เมื่อ user ถูกปิดใช้งาน
        """
        if not email or not email_verified:
            logger.warning("login ปฏิเสธ: อีเมลไม่ยืนยัน provider=%s", provider)
            raise UnverifiedEmailError("provider ไม่ได้ยืนยันอีเมลของบัญชีนี้")

        existing = await self.users.get_by_oauth(provider, provider_user_id)
        if existing is not None:
            self._ensure_active(existing)
            return existing

        user = await self.users.get_by_email(email)
        if user is None:
            user = User(email=email, full_name=full_name)
            self.users.add_user(user)
            await self.db.flush()
            logger.info("สร้าง user ใหม่จาก provider=%s", provider)

        self._ensure_active(user)
        self.users.add_oauth_account(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                email=email,
            )
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    def issue_access_token(self, user: User) -> str:
        """ออก JWT ของแอปเองให้ client ใช้ต่อ."""
        return create_access_token(subject=str(user.id), settings=self.settings)

    @staticmethod
    def _ensure_active(user: User) -> None:
        """Raise ถ้า user ถูกปิดใช้งาน.

        Raises:
            InactiveUserError: เมื่อ ``is_active`` เป็น False
        """
        if not user.is_active:
            raise InactiveUserError("บัญชีนี้ถูกปิดใช้งาน")
