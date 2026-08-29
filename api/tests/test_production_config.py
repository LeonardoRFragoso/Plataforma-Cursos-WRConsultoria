"""Testa fail-closed production configuration validation.

Verifica que a aplicação NÃO inicia em produção com configurações inseguras
e que development/test continua funcionando com defaults.
"""


import pytest

from app.core.secrets import (
    validate_allowed_hosts,
    validate_asaas_mock_mode,
    validate_asaas_webhook_base_url,
    validate_cors_origins,
    validate_e2e_test_mode,
    validate_email_mock_mode,
    validate_mercado_pago_mock_mode,
    validate_production_config,
    validate_rate_limit_enabled,
    validate_secret_key,
    validate_tenant_secret_encryption_key,
)


@pytest.fixture
def prod_settings(monkeypatch):
    """Configura settings simulando produção."""
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "production")
    monkeypatch.setattr("app.core.config.settings.SECRET_KEY", "a" * 32)
    monkeypatch.setattr("app.core.config.settings.TENANT_SECRET_ENCRYPTION_KEY", "key")
    monkeypatch.setattr("app.core.config.settings.ALLOWED_HOSTS", ["api.example.com"])
    monkeypatch.setattr("app.core.config.settings.CORS_ORIGINS", ["https://app.example.com"])
    monkeypatch.setattr("app.core.config.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "MERCADO_PAGO")
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", False)
    monkeypatch.setattr("app.core.config.settings.ASAAS_MOCK_MODE", False)
    monkeypatch.setattr("app.core.config.settings.EMAIL_MOCK_MODE", False)
    monkeypatch.setattr("app.core.config.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_BASE_URL", "https://api.example.com")
    monkeypatch.delenv("E2E_TEST_MODE", raising=False)


class TestIndividualValidators:
    def test_secret_key_too_short(self):
        from app.core.config import settings

        original = settings.SECRET_KEY
        settings.SECRET_KEY = "short"
        try:
            issues = validate_secret_key()
            assert any("at least 32" in i for i in issues)
        finally:
            settings.SECRET_KEY = original

    def test_secret_key_placeholder(self):
        from app.core.config import settings

        original = settings.SECRET_KEY
        settings.SECRET_KEY = "your-secret-key-change-in-production"
        try:
            issues = validate_secret_key()
            assert any("placeholder" in i for i in issues)
        finally:
            settings.SECRET_KEY = original

    def test_allowed_hosts_wildcard(self):
        from app.core.config import settings

        original = settings.ALLOWED_HOSTS
        settings.ALLOWED_HOSTS = ["*"]
        try:
            issues = validate_allowed_hosts()
            assert any("wildcard" in i for i in issues)
        finally:
            settings.ALLOWED_HOSTS = original

    def test_tenant_secret_encryption_key_empty(self):
        from app.core.config import settings

        original = settings.TENANT_SECRET_ENCRYPTION_KEY
        settings.TENANT_SECRET_ENCRYPTION_KEY = ""
        try:
            issues = validate_tenant_secret_encryption_key()
            assert len(issues) == 1
        finally:
            settings.TENANT_SECRET_ENCRYPTION_KEY = original

    def test_mercado_pago_mock_mode_true_when_active(self):
        from app.core.config import settings

        original_mock = settings.MERCADO_PAGO_MOCK_MODE
        original_provider = settings.PAYMENT_PROVIDER
        settings.MERCADO_PAGO_MOCK_MODE = True
        settings.PAYMENT_PROVIDER = "MERCADO_PAGO"
        try:
            issues = validate_mercado_pago_mock_mode()
            assert len(issues) == 1
        finally:
            settings.MERCADO_PAGO_MOCK_MODE = original_mock
            settings.PAYMENT_PROVIDER = original_provider

    def test_mercado_pago_mock_mode_true_when_asaas_active(self):
        from app.core.config import settings

        original_mock = settings.MERCADO_PAGO_MOCK_MODE
        original_provider = settings.PAYMENT_PROVIDER
        settings.MERCADO_PAGO_MOCK_MODE = True
        settings.PAYMENT_PROVIDER = "ASAAS"
        try:
            issues = validate_mercado_pago_mock_mode()
            assert len(issues) == 0
        finally:
            settings.MERCADO_PAGO_MOCK_MODE = original_mock
            settings.PAYMENT_PROVIDER = original_provider

    def test_e2e_test_mode_true(self, monkeypatch):
        monkeypatch.setenv("E2E_TEST_MODE", "true")
        issues = validate_e2e_test_mode()
        assert len(issues) == 1

    def test_cors_wildcard(self):
        from app.core.config import settings

        original = settings.CORS_ORIGINS
        settings.CORS_ORIGINS = ["*"]
        try:
            issues = validate_cors_origins()
            assert any("wildcard" in i for i in issues)
        finally:
            settings.CORS_ORIGINS = original

    def test_cors_localhost(self):
        from app.core.config import settings

        original = settings.CORS_ORIGINS
        settings.CORS_ORIGINS = ["http://localhost:5173"]
        try:
            issues = validate_cors_origins()
            assert any("localhost" in i for i in issues)
        finally:
            settings.CORS_ORIGINS = original

    def test_rate_limit_disabled(self):
        from app.core.config import settings

        original = settings.RATE_LIMIT_ENABLED
        settings.RATE_LIMIT_ENABLED = False
        try:
            issues = validate_rate_limit_enabled()
            assert len(issues) == 1
        finally:
            settings.RATE_LIMIT_ENABLED = original


class TestValidateProductionConfig:
    def test_production_safe_config_does_not_raise(self, prod_settings):
        """Config segura em produção não levanta erro."""
        validate_production_config()  # should not raise

    def test_production_unsafe_secret_key_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.SECRET_KEY", "short")
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_production_config()

    def test_production_placeholder_secret_key_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.SECRET_KEY",
            "your-secret-key-change-in-production",
        )
        with pytest.raises(RuntimeError, match="placeholder"):
            validate_production_config()

    def test_production_wildcard_hosts_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.ALLOWED_HOSTS", ["*"])
        with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
            validate_production_config()

    def test_production_empty_encryption_key_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.TENANT_SECRET_ENCRYPTION_KEY", "")
        with pytest.raises(RuntimeError, match="TENANT_SECRET_ENCRYPTION_KEY"):
            validate_production_config()

    def test_production_mock_mode_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)
        with pytest.raises(RuntimeError, match="MERCADO_PAGO_MOCK_MODE"):
            validate_production_config()

    def test_production_e2e_mode_raises(self, prod_settings, monkeypatch):
        monkeypatch.setenv("E2E_TEST_MODE", "true")
        with pytest.raises(RuntimeError, match="E2E_TEST_MODE"):
            validate_production_config()

    def test_production_cors_wildcard_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.CORS_ORIGINS", ["*"])
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            validate_production_config()

    def test_production_rate_limit_disabled_raises(self, prod_settings, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.RATE_LIMIT_ENABLED", False)
        with pytest.raises(RuntimeError, match="RATE_LIMIT_ENABLED"):
            validate_production_config()

    def test_development_does_not_validate(self, monkeypatch):
        """Em development, validate_production_config não faz nada."""
        monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.core.config.settings.SECRET_KEY", "short")
        # Should NOT raise
        validate_production_config()


class TestProviderAwareValidatorMatrix:
    """Provider-aware production validation matrix.

    Verifies that production validation is fail-closed for the ACTIVE
    provider but does not block startup for inactive/legacy providers.
    """

    def test_asaas_active_mp_mock_does_not_block(self, prod_settings, monkeypatch):
        """Asaas active + Mercado Pago mock → PASS (MP is legacy)."""
        monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "ASAAS")
        monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)
        monkeypatch.setattr("app.core.config.settings.ASAAS_MOCK_MODE", False)
        monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_BASE_URL", "https://api.example.com")
        validate_production_config()  # should not raise

    def test_asaas_active_asaas_mock_blocks(self, prod_settings, monkeypatch):
        """Asaas active + ASAAS_MOCK_MODE=true → FAIL."""
        monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "ASAAS")
        monkeypatch.setattr("app.core.config.settings.ASAAS_MOCK_MODE", True)
        with pytest.raises(RuntimeError, match="ASAAS_MOCK_MODE"):
            validate_production_config()

    def test_asaas_active_webhook_missing_blocks(self, prod_settings, monkeypatch):
        """Asaas active + webhook base URL missing → FAIL."""
        monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "ASAAS")
        monkeypatch.setattr("app.core.config.settings.ASAAS_MOCK_MODE", False)
        monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_BASE_URL", "")
        with pytest.raises(RuntimeError, match="ASAAS_WEBHOOK_BASE_URL"):
            validate_production_config()

    def test_mp_active_mp_mock_blocks(self, prod_settings, monkeypatch):
        """Mercado Pago active + MP mock → FAIL."""
        monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "MERCADO_PAGO")
        monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)
        with pytest.raises(RuntimeError, match="MERCADO_PAGO_MOCK_MODE"):
            validate_production_config()

    def test_mp_active_asaas_mock_does_not_block(self, prod_settings, monkeypatch):
        """Mercado Pago active + Asaas mock → PASS (Asaas is inactive)."""
        monkeypatch.setattr("app.core.config.settings.PAYMENT_PROVIDER", "MERCADO_PAGO")
        monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", False)
        monkeypatch.setattr("app.core.config.settings.ASAAS_MOCK_MODE", True)
        monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_BASE_URL", "")
        validate_production_config()  # should not raise

    def test_email_disabled_mock_mode_does_not_block(self, prod_settings, monkeypatch):
        """EMAIL_ENABLED=false + EMAIL_MOCK_MODE=true → PASS."""
        monkeypatch.setattr("app.core.config.settings.EMAIL_ENABLED", False)
        monkeypatch.setattr("app.core.config.settings.EMAIL_MOCK_MODE", True)
        validate_production_config()  # should not raise

    def test_email_enabled_mock_mode_blocks(self, prod_settings, monkeypatch):
        """EMAIL_ENABLED=true + EMAIL_MOCK_MODE=true → FAIL."""
        monkeypatch.setattr("app.core.config.settings.EMAIL_ENABLED", True)
        monkeypatch.setattr("app.core.config.settings.EMAIL_MOCK_MODE", True)
        with pytest.raises(RuntimeError, match="EMAIL_MOCK_MODE"):
            validate_production_config()
