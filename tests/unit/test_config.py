"""ตรวจ settings layer."""

from app.core.config import AppEnv, LazadaSettings, Settings


class TestLazadaSettings:
    def test_is_configured_false_when_credentials_missing(self):
        settings = LazadaSettings(app_key="", app_secret="", _env_file=None)
        assert settings.is_configured is False

    def test_is_configured_true_when_credentials_present(self):
        settings = LazadaSettings(app_key="141659", app_secret="s", _env_file=None)
        assert settings.is_configured is True

    def test_app_secret_is_not_exposed_in_repr(self):
        settings = LazadaSettings(app_key="141659", app_secret="real-secret")
        assert "real-secret" not in repr(settings)


class TestSettings:
    def test_is_production_false_for_local(self):
        assert Settings(app_env=AppEnv.LOCAL, _env_file=None).is_production is False

    def test_is_production_true_for_production(self):
        settings = Settings(app_env=AppEnv.PRODUCTION, _env_file=None)
        assert settings.is_production is True
