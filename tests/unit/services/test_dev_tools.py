"""ตรวจเครื่องมือ dev — ต้องใช้ไม่ได้บน production."""

import pytest

from app.marketplaces.base import Platform
from app.services.dev_tools import (
    DEV_EMAIL,
    DevToolsDisabledError,
    finish_manual_authorization,
    issue_dev_token,
    start_manual_authorization,
)


class TestIssueDevToken:
    async def test_creates_dev_user_and_returns_valid_token(
        self, db_session, security_settings
    ):
        # Act
        token = await issue_dev_token(
            db_session, security_settings, is_production=False
        )
        # Assert
        from app.core.security import decode_access_token
        from app.repositories.user_repository import UserRepository

        user = await UserRepository(db_session).get_by_email(DEV_EMAIL)
        assert user is not None
        assert decode_access_token(token, security_settings) == str(user.id)

    async def test_reuses_existing_dev_user(self, db_session, security_settings):
        first = await issue_dev_token(
            db_session, security_settings, is_production=False
        )
        second = await issue_dev_token(
            db_session, security_settings, is_production=False
        )
        from app.core.security import decode_access_token

        assert decode_access_token(first, security_settings) == decode_access_token(
            second, security_settings
        )

    async def test_refuses_on_production(self, db_session, security_settings):
        """กันเผลอออก token ให้ตัวเองบน production."""
        with pytest.raises(DevToolsDisabledError):
            await issue_dev_token(db_session, security_settings, is_production=True)


class TestManualAuthorization:
    async def test_authorize_then_exchange_links_shop(
        self, db_session, fake_client, cipher
    ):
        # Arrange
        url = await start_manual_authorization(
            db_session, fake_client, cipher, Platform.LAZADA
        )
        state = url.split("state=")[1]
        # Act
        account_id = await finish_manual_authorization(
            db_session, fake_client, cipher, Platform.LAZADA, "code-1", state
        )
        # Assert
        assert account_id == "100392024"

    async def test_exchange_with_wrong_state_raises(
        self, db_session, fake_client, cipher
    ):
        from app.services.oauth_service import InvalidOAuthStateError

        with pytest.raises(InvalidOAuthStateError):
            await finish_manual_authorization(
                db_session, fake_client, cipher, Platform.LAZADA, "c", "forged"
            )


class TestDevEmailIsUsable:
    def test_dev_email_passes_response_schema_validation(self):
        """regression: เดิมใช้ .local ซึ่ง EmailStr ปฏิเสธ ทำให้ /auth/me พัง 500

        TLD สงวน (.local/.test/.example/.invalid) ใช้กับ EmailStr ไม่ได้
        """
        from app.schemas.auth import UserOut

        user = UserOut(id=1, email=DEV_EMAIL, full_name="Dev User", is_active=True)
        assert user.email == DEV_EMAIL

    async def test_dev_user_can_be_serialised_after_creation(
        self, db_session, security_settings
    ):
        from app.repositories.user_repository import UserRepository
        from app.schemas.auth import UserOut

        await issue_dev_token(db_session, security_settings, is_production=False)
        user = await UserRepository(db_session).get_by_email(DEV_EMAIL)
        assert UserOut.model_validate(user).email == DEV_EMAIL


class TestBuildTestEmailBody:
    def test_body_mentions_environment(self):
        from app.services.dev_tools import build_test_email_body

        body = build_test_email_body("local")
        assert "local" in body
        assert "Streamora" in body

    def test_body_is_plain_text_without_secrets(self):
        from app.services.dev_tools import build_test_email_body

        body = build_test_email_body("production")
        assert "password" not in body.lower()
        assert "<" not in body
