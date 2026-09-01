"""ตรวจการเข้ารหัส token ตาม STANDARDS section 8.2."""

import pytest
from cryptography.fernet import Fernet

from app.core.security import TokenCipher, TokenCipherError, generate_key


class TestTokenCipher:
    def test_encrypt_then_decrypt_returns_original(self, cipher):
        # Arrange
        token = "50000600a1b2c3d4e5f6"
        # Act
        encrypted = cipher.encrypt(token)
        # Assert
        assert encrypted != token
        assert cipher.decrypt(encrypted) == token

    def test_encrypt_same_value_twice_gives_different_ciphertext(self, cipher):
        """Fernet ใส่ IV สุ่ม — ciphertext ต้องไม่ซ้ำแม้ plaintext เดิม."""
        assert cipher.encrypt("same") != cipher.encrypt("same")

    def test_decrypt_with_wrong_key_raises(self):
        # Arrange
        encrypted = TokenCipher(Fernet.generate_key().decode()).encrypt("secret")
        other = TokenCipher(Fernet.generate_key().decode())
        # Act & Assert
        with pytest.raises(TokenCipherError):
            other.decrypt(encrypted)

    def test_decrypt_corrupted_ciphertext_raises(self, cipher):
        with pytest.raises(TokenCipherError):
            cipher.decrypt("not-a-valid-ciphertext")

    def test_invalid_key_raises_on_construction(self):
        with pytest.raises(TokenCipherError):
            TokenCipher("too-short")


class TestGenerateKey:
    def test_generated_key_is_usable(self):
        key = generate_key()
        assert TokenCipher(key).decrypt(TokenCipher(key).encrypt("x")) == "x"


class TestPasswordHashing:
    def test_hash_then_verify_succeeds(self):
        from app.core.security import hash_password, verify_password

        hashed = hash_password("Str0ngPass!")
        assert hashed != "Str0ngPass!"
        assert verify_password("Str0ngPass!", hashed) is True

    def test_verify_wrong_password_fails(self):
        from app.core.security import hash_password, verify_password

        assert verify_password("wrong", hash_password("Str0ngPass!")) is False

    def test_verify_against_garbage_hash_returns_false_not_crash(self):
        from app.core.security import verify_password

        assert verify_password("x", "not-a-hash") is False

    def test_same_password_hashes_differently(self):
        """salt สุ่ม — hash เดิมซ้ำต้องไม่เหมือนกัน."""
        from app.core.security import hash_password

        assert hash_password("same") != hash_password("same")


class TestAccessToken:
    def test_create_then_decode_returns_subject(self, security_settings):
        from app.core.security import create_access_token, decode_access_token

        token = create_access_token("42", security_settings)
        assert decode_access_token(token, security_settings) == "42"

    def test_expired_token_is_rejected(self, security_settings):
        from datetime import UTC, datetime, timedelta

        from app.core.security import (
            InvalidAccessTokenError,
            create_access_token,
            decode_access_token,
        )

        past = datetime.now(UTC) - timedelta(hours=2)
        token = create_access_token("42", security_settings, now=past)
        with pytest.raises(InvalidAccessTokenError):
            decode_access_token(token, security_settings)

    def test_token_signed_with_other_secret_is_rejected(self, security_settings):
        from app.core.config import SecuritySettings
        from app.core.security import (
            InvalidAccessTokenError,
            create_access_token,
            decode_access_token,
        )

        other = SecuritySettings(
            secret_key="s" * 32,
            jwt_secret_key="different-jwt-secret-at-least-32-bytes",
            _env_file=None,
        )
        token = create_access_token("42", other)
        with pytest.raises(InvalidAccessTokenError):
            decode_access_token(token, security_settings)

    def test_garbage_token_is_rejected(self, security_settings):
        from app.core.security import InvalidAccessTokenError, decode_access_token

        with pytest.raises(InvalidAccessTokenError):
            decode_access_token("not.a.jwt", security_settings)


class TestSecuritySettings:
    def test_secrets_must_be_distinct(self):
        from app.core.config import SecuritySettings

        same = SecuritySettings(secret_key="x", jwt_secret_key="x", _env_file=None)
        assert same.secrets_are_distinct is False

    def test_distinct_secrets_pass(self, security_settings):
        assert security_settings.secrets_are_distinct is True

    def test_short_secret_is_flagged_weak(self):
        """HMAC-SHA256 ต้องการ key >= 32 bytes ตาม RFC 7518 3.2."""
        from app.core.config import SecuritySettings

        weak = SecuritySettings(secret_key="a", jwt_secret_key="b", _env_file=None)
        assert weak.secrets_are_strong is False

    def test_long_secret_passes_strength_check(self, security_settings):
        assert security_settings.secrets_are_strong is True
