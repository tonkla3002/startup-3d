"""ฟังก์ชันช่วยทดสอบ OAuth flow ด้วยมือระหว่าง dev.

แยกมาไว้ใน app/ เพื่อให้มี test ครอบตาม PROJECT_RULES 5.1
(``scripts/`` เป็นแค่ตัวห่อ argparse บาง ๆ)
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SecuritySettings
from app.core.exceptions import StreamoraError
from app.core.security import TokenCipher, create_access_token
from app.marketplaces.base import MarketplaceClient, Platform
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.oauth_service import OAuthService

logger = logging.getLogger(__name__)

# ห้ามใช้ TLD สงวน (.local/.test/.example) — EmailStr ปฏิเสธ ทำให้ /auth/me พัง 500
DEV_EMAIL = "dev@streamora.dev"


class DevToolsDisabledError(StreamoraError):
    """เครื่องมือ dev ถูกเรียกใช้บน production."""


async def issue_dev_token(
    db: AsyncSession,
    settings: SecuritySettings,
    is_production: bool,
    email: str = DEV_EMAIL,
) -> str:
    """สร้าง user สำหรับ dev แล้วออก JWT ให้ ใช้ทดสอบ endpoint ที่ต้องล็อกอิน.

    Args:
        db: session
        settings: secret สำหรับเซ็น JWT
        is_production: ถ้า True จะปฏิเสธทันที
        email: อีเมลของ user ที่จะสร้าง/ใช้ซ้ำ

    Returns:
        JWT ที่ใช้ใส่ header ``Authorization: Bearer ...``

    Raises:
        DevToolsDisabledError: เมื่อเรียกใช้บน production
    """
    if is_production:
        raise DevToolsDisabledError("ห้ามออก dev token บน production")

    users = UserRepository(db)
    user = await users.get_by_email(email)
    if user is None:
        user = User(email=email, full_name="Dev User")
        users.add_user(user)
        await db.commit()
        await db.refresh(user)
        logger.info("สร้าง dev user %s", email)

    return create_access_token(str(user.id), settings)


async def start_manual_authorization(
    db: AsyncSession, client: MarketplaceClient, cipher: TokenCipher, platform: Platform
) -> str:
    """สร้าง authorize URL พร้อมบันทึก state ลง DB (เหมือนที่ endpoint ทำ)."""
    service = OAuthService(db=db, client=client, cipher=cipher)
    return await service.start_authorization(platform)


async def finish_manual_authorization(
    db: AsyncSession,
    client: MarketplaceClient,
    cipher: TokenCipher,
    platform: Platform,
    code: str,
    state: str,
) -> str:
    """แลก code ที่ copy มาจาก address bar เป็น token แล้วบันทึกร้าน.

    Returns:
        account_id ของร้านที่ผูกสำเร็จ
    """
    service = OAuthService(db=db, client=client, cipher=cipher)
    shop = await service.complete_authorization(platform, code=code, state=state)
    return shop.account_id
