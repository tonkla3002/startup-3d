"""ตรวจ AuthService — social login ตาม PROJECT_RULES section 4.6."""

import pytest

from app.repositories.user_repository import UserRepository
from app.services.auth_service import (
    AuthService,
    InactiveUserError,
    UnverifiedEmailError,
)

PROFILE = {
    "provider": "google",
    "provider_user_id": "g-123",
    "email": "new@example.com",
    "email_verified": True,
    "full_name": "New User",
}


class TestLoginOrCreateUser:
    async def test_login_new_user_creates_account(self, db_session, security_settings):
        # Arrange
        service = AuthService(db=db_session, settings=security_settings)
        # Act
        user = await service.login_or_create_user(**PROFILE)
        # Assert
        assert user.email == "new@example.com"
        assert user.id is not None

    async def test_login_existing_oauth_account_returns_same_user(
        self, db_session, security_settings, user_factory
    ):
        """login ซ้ำต้อง map กลับ user เดิม ไม่สร้างซ้ำ (PROJECT_RULES 4.5)."""
        # Arrange
        existing = await user_factory(
            email="dup@example.com", provider="google", provider_user_id="g-123"
        )
        service = AuthService(db=db_session, settings=security_settings)
        # Act
        user = await service.login_or_create_user(
            **{**PROFILE, "email": "dup@example.com"}
        )
        # Assert
        assert user.id == existing.id

    async def test_same_email_different_provider_links_to_existing_user(
        self, db_session, security_settings, user_factory
    ):
        """คนเดิม login ด้วย GitHub หลังเคยใช้ Google ต้องเป็น user เดียวกัน."""
        # Arrange
        existing = await user_factory(
            email="same@example.com", provider="google", provider_user_id="g-1"
        )
        service = AuthService(db=db_session, settings=security_settings)
        # Act
        user = await service.login_or_create_user(
            provider="github",
            provider_user_id="gh-9",
            email="same@example.com",
            email_verified=True,
        )
        # Assert
        assert user.id == existing.id

    @pytest.mark.parametrize(
        ("email", "verified"),
        [(None, True), ("x@example.com", False), ("", True)],
    )
    async def test_missing_or_unverified_email_is_rejected(
        self, db_session, security_settings, email, verified
    ):
        """ห้าม trust email ที่ provider ไม่ยืนยัน (PROJECT_RULES 4.5)."""
        service = AuthService(db=db_session, settings=security_settings)
        with pytest.raises(UnverifiedEmailError):
            await service.login_or_create_user(
                provider="google",
                provider_user_id="g-2",
                email=email,
                email_verified=verified,
            )

    async def test_inactive_user_cannot_login(
        self, db_session, security_settings, user_factory
    ):
        # Arrange
        await user_factory(
            email="off@example.com",
            is_active=False,
            provider="google",
            provider_user_id="g-off",
        )
        service = AuthService(db=db_session, settings=security_settings)
        # Act & Assert
        with pytest.raises(InactiveUserError):
            await service.login_or_create_user(
                provider="google",
                provider_user_id="g-off",
                email="off@example.com",
                email_verified=True,
            )

    async def test_no_duplicate_user_when_logging_in_twice(
        self, db_session, security_settings
    ):
        # Arrange
        service = AuthService(db=db_session, settings=security_settings)
        first = await service.login_or_create_user(**PROFILE)
        # Act
        second = await service.login_or_create_user(**PROFILE)
        # Assert
        assert first.id == second.id
        assert await UserRepository(db_session).get_by_email("new@example.com")


class TestIssueAccessToken:
    async def test_issued_token_decodes_back_to_user_id(
        self, db_session, security_settings
    ):
        from app.core.security import decode_access_token

        service = AuthService(db=db_session, settings=security_settings)
        user = await service.login_or_create_user(**PROFILE)
        token = service.issue_access_token(user)
        assert decode_access_token(token, security_settings) == str(user.id)
