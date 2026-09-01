"""Fixture กลางของ test suite ทั้งหมด.

DB test ใช้ **Postgres จริง** ผ่าน testcontainers ตาม PROJECT_RULES 5.2b —
ห้าม mock SQLAlchemy session และแต่ละ test rollback ทิ้งเพื่อไม่ให้ข้อมูลรั่วถึงกัน
"""

import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("LAZADA_APP_KEY", "141659")
os.environ.setdefault("LAZADA_APP_SECRET", "test-secret")
os.environ.setdefault("SECRET_KEY", "test-session-secret-0123456789abcdef")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-different-0123456789")
os.environ.setdefault(
    "LAZADA_REDIRECT_URI", "https://test.local/api/v1/auth/lazada/callback"
)

import httpx
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.core.config import LazadaSettings
from app.core.security import TokenCipher
from app.marketplaces.lazada.client import LazadaClient

# ค่าคงที่สำหรับ golden test — ห้ามเปลี่ยนโดยไม่คำนวณ signature ใหม่
TEST_APP_KEY = "141659"
TEST_APP_SECRET = "test-secret"
TEST_TIMESTAMP_MS = "1755000000000"
TEST_API_BASE = "https://api.lazada.test/rest"
TEST_AUTH_BASE = "https://auth.lazada.test/rest"


@pytest.fixture
def app_key() -> str:
    """App Key ปลอมสำหรับ test."""
    return TEST_APP_KEY


@pytest.fixture
def app_secret() -> str:
    """App Secret ปลอมสำหรับ test — ไม่ใช่ค่าจริง."""
    return TEST_APP_SECRET


@pytest.fixture
def timestamp_ms() -> str:
    """Timestamp คงที่ เพื่อให้ signature เป็น deterministic."""
    return TEST_TIMESTAMP_MS


@pytest.fixture
def lazada_settings() -> LazadaSettings:
    """Settings ของ Lazada ที่ชี้ไปโดเมนปลอม (กันยิงของจริงโดยอุบัติเหตุ)."""
    return LazadaSettings(
        app_key=TEST_APP_KEY,
        app_secret=TEST_APP_SECRET,
        api_base_url=TEST_API_BASE,
        auth_base_url=TEST_AUTH_BASE,
        authorize_url="https://auth.lazada.test/oauth/authorize",
        redirect_uri="https://test.local/api/v1/auth/lazada/callback",
        _env_file=None,
    )


@pytest.fixture
def cipher() -> TokenCipher:
    """TokenCipher ที่ใช้ key สุ่มเฉพาะ test นี้."""
    return TokenCipher(Fernet.generate_key().decode())


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """httpx client สำหรับ inject เข้า LazadaClient (respx จะ mock ให้)."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def lazada_client(http_client, lazada_settings) -> LazadaClient:
    """LazadaClient ที่ไม่หน่วงเวลาจริงตอน retry."""

    async def _no_sleep(_seconds: float) -> None:
        return None

    return LazadaClient(
        http=http_client,
        settings=lazada_settings,
        max_attempts=3,
        backoff_seconds=0.0,
        sleep=_no_sleep,
    )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client ที่ยิงเข้า FastAPI app ผ่าน ASGI โดยตรง (ไม่เปิด network จริง)."""
    from app.main import create_app

    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


# --------------------------------------------------------------------------- #
# Database fixtures — ใช้ Postgres จริงผ่าน testcontainers
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Spin Postgres container ชั่วคราวสำหรับ test suite นี้.

    ข้าม test ทั้งหมดที่ต้องใช้ DB ถ้าเครื่องไม่มี Docker รันอยู่
    """
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:  # pragma: no cover - รองรับ testcontainers รุ่นเก่า
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError:
            pytest.skip("ไม่มี testcontainers")

    try:
        with PostgresContainer("postgres:16-alpine", driver="asyncpg") as container:
            yield container.get_connection_url()
    except Exception as exc:  # pragma: no cover - ขึ้นกับ environment
        pytest.skip(f"Docker ใช้งานไม่ได้: {exc}")


@pytest.fixture(scope="session")
def migrated_db(postgres_url) -> str:
    """รัน ``alembic upgrade head`` กับ test DB ตาม PROJECT_RULES 5.2b.

    fixture นี้เป็น **sync** โดยตั้งใจ — alembic/env.py เรียก ``asyncio.run()``
    ซึ่งจะพังถ้าถูกเรียกจากใน event loop ที่กำลังรันอยู่
    """
    from alembic.config import Config

    from alembic import command
    from app.core.config import get_settings

    os.environ["DATABASE_URL"] = postgres_url
    get_settings.cache_clear()

    command.upgrade(Config("alembic.ini"), "head")
    return postgres_url


@pytest.fixture(scope="session")
async def db_engine(migrated_db):
    """Engine ที่ชี้ไป test DB ซึ่ง migrate เรียบร้อยแล้ว."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated_db)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """เปิด transaction ก่อน test แล้ว rollback หลัง test — DB สะอาดเสมอ."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def api_client(db_session) -> AsyncIterator[AsyncClient]:
    """Client ที่ override get_db ให้ใช้ session ของ test (rollback ได้)."""
    from app.db.session import get_db
    from app.main import create_app

    application = create_app()

    async def _override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        application.state.http_client = httpx.AsyncClient()
        yield http
        await application.state.http_client.aclose()
    application.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Fake marketplace client — ใช้แทน client จริงในชั้น service/API test
# --------------------------------------------------------------------------- #


class FakeMarketplaceClient:
    """Client ปลอมที่ implement contract เดียวกับของจริง.

    ใช้แทน HTTP call ในชั้น service/API test — ไม่มี network เข้ามาเกี่ยวเลย
    """

    def __init__(self, bundle=None, signature_valid: bool = True) -> None:
        from app.marketplaces.base import Platform

        self.platform = Platform.LAZADA
        self._bundle = bundle
        self._signature_valid = signature_valid
        self.exchange_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def build_authorize_url(self, state: str) -> str:
        return f"https://auth.lazada.test/oauth/authorize?state={state}"

    async def exchange_code(self, code: str):
        self.exchange_calls.append(code)
        return self._bundle

    async def refresh_token(self, refresh_token: str):
        self.refresh_calls.append(refresh_token)
        return self._bundle

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        return self._signature_valid


@pytest.fixture
def token_bundle():
    """TokenBundle ตัวอย่างที่ยังไม่หมดอายุ."""
    from datetime import timedelta

    from app.marketplaces.base import TokenBundle

    now = datetime.now(UTC)
    return TokenBundle(
        access_token="at-new",
        refresh_token="rt-new",
        expires_at=now + timedelta(days=7),
        refresh_expires_at=now + timedelta(days=30),
        account_id="100392024",
    )


@pytest.fixture
def fake_client(token_bundle):
    """Client ปลอมที่คืน token_bundle เสมอ."""
    return FakeMarketplaceClient(bundle=token_bundle)


@pytest.fixture
def shop_factory(db_session, cipher):
    """สร้างร้านลง DB จริงสำหรับ test."""
    from datetime import timedelta

    from app.marketplaces.base import Platform
    from app.models.marketplace_shop import MarketplaceShop

    async def _create(
        account_id: str = "100392024",
        platform: Platform = Platform.LAZADA,
        expires_in: timedelta = timedelta(days=7),
        access_token: str = "at-old",
        refresh_token: str = "rt-old",
        is_active: bool = True,
    ) -> MarketplaceShop:
        now = datetime.now(UTC)
        shop = MarketplaceShop(
            platform=platform,
            account_id=account_id,
            access_token_encrypted=cipher.encrypt(access_token),
            refresh_token_encrypted=cipher.encrypt(refresh_token),
            expires_at=now + expires_in,
            refresh_expires_at=now + timedelta(days=30),
            is_active=is_active,
        )
        db_session.add(shop)
        await db_session.commit()
        await db_session.refresh(shop)
        return shop

    return _create


# --------------------------------------------------------------------------- #
# Auth fixtures (PROJECT_RULES section 4)
# --------------------------------------------------------------------------- #


@pytest.fixture
def security_settings():
    """SecuritySettings สำหรับ test — secret สองตัวต่างกันตามกฎ 4.4."""
    from app.core.config import SecuritySettings

    return SecuritySettings(
        secret_key="session-secret-that-is-at-least-32-bytes",
        jwt_secret_key="jwt-secret-that-is-also-at-least-32-bytes",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        _env_file=None,
    )


@pytest.fixture
def user_factory(db_session):
    """สร้าง user (และผูก oauth account ได้) ลง DB จริง."""
    from app.models.oauth_account import OAuthAccount
    from app.models.user import User

    async def _create(
        email: str = "user@example.com",
        is_active: bool = True,
        provider: str | None = None,
        provider_user_id: str | None = None,
    ) -> User:
        user = User(email=email, full_name="Test User", is_active=is_active)
        db_session.add(user)
        await db_session.flush()
        if provider and provider_user_id:
            db_session.add(
                OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    email=email,
                )
            )
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def auth_headers():
    """สร้าง header Authorization จาก user.

    ต้องเซ็นด้วย settings **ตัวเดียวกับที่แอปใช้** (อ่านจาก env) ไม่ใช่ fixture
    ``security_settings`` ที่ใช้เฉพาะ unit test ไม่งั้นจะได้ 401
    """
    from app.core.config import get_security_settings
    from app.core.security import create_access_token

    def _headers(user) -> dict[str, str]:
        token = create_access_token(str(user.id), get_security_settings())
        return {"Authorization": f"Bearer {token}"}

    return _headers


class FakeOAuthClient:
    """Authlib client ปลอม — ไม่ยิง Google/GitHub จริงตาม PROJECT_RULES 4.6."""

    def __init__(self, token=None, error=None, github_user=None, github_emails=None):
        self._token = token or {}
        self._error = error
        self._github_user = github_user
        self._github_emails = github_emails or []
        self.authorize_calls = 0

    async def authorize_redirect(self, request, redirect_uri):
        from starlette.responses import RedirectResponse

        self.authorize_calls += 1
        return RedirectResponse(url=f"https://provider.test/consent?rd={redirect_uri}")

    async def authorize_access_token(self, request):
        if self._error is not None:
            raise self._error
        return self._token

    async def userinfo(self, token=None):
        return self._token.get("userinfo", {})

    async def get(self, path, token=None):
        class _Response:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def json(self):
                return self._payload

        if path == "user":
            return _Response(self._github_user or {})
        return _Response(self._github_emails)


class FakeOAuthRegistry:
    """Registry ปลอมที่คืน FakeOAuthClient."""

    def __init__(self, client=None):
        self._client = client

    def create_client(self, provider: str):
        return self._client
