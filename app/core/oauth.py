"""Authlib OAuth client สำหรับ social login เข้าระบบเรา.

ใช้ Authorization Code Flow + PKCE ตาม PROJECT_RULES section 4.1
Authlib จัดการ ``state``/``nonce``/PKCE ให้อัตโนมัติเมื่อใช้
``authorize_redirect`` คู่กับ ``authorize_access_token`` — ห้าม bypass
"""

import os

from authlib.integrations.starlette_client import OAuth

from app.core.config import OAuthProviderSettings

GOOGLE = "google"
GITHUB = "github"
SUPPORTED_PROVIDERS = frozenset({GOOGLE, GITHUB})

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE_URL = "https://api.github.com/"

# hardcode แทน server_metadata_url เพราะ VPS outbound ถูกบล็อก
# ถ้ามี GOOGLE_PROXY_BASE_URL (Cloudflare Worker) ใช้ proxy แทนเพื่อเลี่ยง firewall
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_PROXY = os.getenv("GOOGLE_PROXY_BASE_URL", "").rstrip("/")
GOOGLE_TOKEN_URL = f"{_PROXY}/token" if _PROXY else "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = f"{_PROXY}/v1/userinfo" if _PROXY else "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_JWK_SET_URL = f"{_PROXY}/oauth2/v3/certs" if _PROXY else "https://www.googleapis.com/oauth2/v3/certs"


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
            authorize_url=GOOGLE_AUTHORIZE_URL,
            access_token_url=GOOGLE_TOKEN_URL,
            userinfo_endpoint=GOOGLE_USERINFO_URL,
            jwks_uri=GOOGLE_JWK_SET_URL,
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
