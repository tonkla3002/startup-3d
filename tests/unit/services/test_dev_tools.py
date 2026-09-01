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
