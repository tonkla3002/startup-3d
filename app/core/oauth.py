"""Authlib OAuth client สำหรับ social login เข้าระบบเรา.

ใช้ Authorization Code Flow + PKCE ตาม PROJECT_RULES section 4.1
Authlib จัดการ ``state``/``nonce``/PKCE ให้อัตโนมัติเมื่อใช้
``authorize_redirect`` คู่กับ ``authorize_access_token`` — ห้าม bypass
"""

from authlib.integrations.starlette_client import OAuth

from app.core.config import OAuthProviderSettings

GOOGLE = "google"
GITHUB = "github"
SUPPORTED_PROVIDERS = frozenset({GOOGLE, GITHUB})

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE_URL = "https://api.github.com/"


def build_oauth(settings: OAuthProviderSettings) -> OAuth:
    """ลงทะเบียน provider ที่ตั้ง credential ไว้ครบ.

    Args:
        settings: credential ของ provider ต่าง ๆ

    Returns:
        OAuth registry ที่พร้อมใช้
    """
    oauth = OAuth()

    if settings.is_enabled(GOOGLE):
        oauth.register(
            name=GOOGLE,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={
                "scope": "openid email profile",
                "code_challenge_method": "S256",
            },
        )

    if settings.is_enabled(GITHUB):
        oauth.register(
            name=GITHUB,
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret.get_secret_value(),
            authorize_url=GITHUB_AUTHORIZE_URL,
            access_token_url=GITHUB_TOKEN_URL,
            api_base_url=GITHUB_API_BASE_URL,
            client_kwargs={"scope": "read:user user:email"},
        )

    return oauth
