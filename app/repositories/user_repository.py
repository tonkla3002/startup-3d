"""Data access ของ users และ oauth_accounts."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_account import OAuthAccount
from app.models.user import User


class UserRepository:
    """Query ที่เกี่ยวกับผู้ใช้ระบบทั้งหมดอยู่ที่นี่."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: int) -> User | None:
        """หา user จาก id."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """หา user จากอีเมล."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: str, provider_user_id: str) -> User | None:
        """หา user จาก identity ของ provider."""
        result = await self.db.execute(
            select(User)
            .join(OAuthAccount, OAuthAccount.user_id == User.id)
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    def add_user(self, user: User) -> User:
        """เพิ่ม user ใหม่เข้า session (commit ที่ service)."""
        self.db.add(user)
        return user

    def add_oauth_account(self, account: OAuthAccount) -> OAuthAccount:
        """ผูก identity ของ provider เข้ากับ user (commit ที่ service)."""
        self.db.add(account)
        return account
