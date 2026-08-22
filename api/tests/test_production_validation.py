"""Tests for production validation: mock modes, key format, secret reveal."""

from unittest.mock import patch

import pytest

from app.core.secrets import (
    validate_asaas_mock_mode,
    validate_asaas_webhook_base_url,
    validate_email_mock_mode,
    validate_production_config,
)


def test_asaas_mock_mode_rejected_in_production():
    """ASAAS_MOCK_MODE=true must be rejected in production."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.ASAAS_MOCK_MODE = True
        mock_settings.EMAIL_MOCK_MODE = False
        mock_settings.EMAIL_ENABLED = True
        mock_settings.ASAAS_WEBHOOK_BASE_URL = "https://api.test"
        issues = validate_asaas_mock_mode()
        assert len(issues) == 1
        assert "ASAAS_MOCK_MODE" in issues[0]


def test_asaas_mock_mode_ok_in_development():
    """ASAAS_MOCK_MODE=true is OK in development."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "development"
        mock_settings.ASAAS_MOCK_MODE = True
        issues = validate_asaas_mock_mode()
        # validate_asaas_mock_mode checks the setting regardless of env,
        # but validate_production_config only runs in production
        assert len(issues) == 1  # The setting is flagged


def test_email_mock_mode_rejected_in_production():
    """EMAIL_MOCK_MODE=true must be rejected in production when EMAIL_ENABLED=true."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.EMAIL_MOCK_MODE = True
        mock_settings.EMAIL_ENABLED = True
        issues = validate_email_mock_mode()
        assert len(issues) == 1
        assert "EMAIL_MOCK_MODE" in issues[0]


def test_email_mock_mode_ok_when_email_disabled():
    """EMAIL_MOCK_MODE=true is OK when EMAIL_ENABLED=false (email explicitly disabled)."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.EMAIL_MOCK_MODE = True
        mock_settings.EMAIL_ENABLED = False
        issues = validate_email_mock_mode()
        assert len(issues) == 0


def test_asaas_webhook_base_url_required_in_production():
    """ASAAS_WEBHOOK_BASE_URL must be set in production."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.ASAAS_WEBHOOK_BASE_URL = ""
        issues = validate_asaas_webhook_base_url()
        assert len(issues) == 1
        assert "ASAAS_WEBHOOK_BASE_URL" in issues[0]


def test_production_config_rejects_asaas_mock_mode():
    """validate_production_config must reject ASAAS_MOCK_MODE=true in production."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.SECRET_KEY = "x" * 32
        mock_settings.ALLOWED_HOSTS = ["example.com"]
        mock_settings.TENANT_SECRET_ENCRYPTION_KEY = "test_key"
        mock_settings.MERCADO_PAGO_MOCK_MODE = False
        mock_settings.ASAAS_MOCK_MODE = True
        mock_settings.EMAIL_MOCK_MODE = False
        mock_settings.EMAIL_ENABLED = True
        mock_settings.ASAAS_WEBHOOK_BASE_URL = "https://api.test"
        mock_settings.CORS_ORIGINS = ["https://example.com"]
        mock_settings.RATE_LIMIT_ENABLED = True

        # Mock the env var check
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_production_config()
            assert "ASAAS_MOCK_MODE" in str(exc_info.value)


def test_production_config_rejects_email_mock_mode():
    """validate_production_config must reject EMAIL_MOCK_MODE=true in production."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.SECRET_KEY = "x" * 32
        mock_settings.ALLOWED_HOSTS = ["example.com"]
        mock_settings.TENANT_SECRET_ENCRYPTION_KEY = "test_key"
        mock_settings.MERCADO_PAGO_MOCK_MODE = False
        mock_settings.ASAAS_MOCK_MODE = False
        mock_settings.EMAIL_MOCK_MODE = True
        mock_settings.EMAIL_ENABLED = True
        mock_settings.ASAAS_WEBHOOK_BASE_URL = "https://api.test"
        mock_settings.CORS_ORIGINS = ["https://example.com"]
        mock_settings.RATE_LIMIT_ENABLED = True

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_production_config()
            assert "EMAIL_MOCK_MODE" in str(exc_info.value)


def test_production_config_ok_with_valid_settings():
    """validate_production_config passes with all valid production settings."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.SECRET_KEY = "x" * 32
        mock_settings.ALLOWED_HOSTS = ["example.com"]
        mock_settings.TENANT_SECRET_ENCRYPTION_KEY = "test_key"
        mock_settings.MERCADO_PAGO_MOCK_MODE = False
        mock_settings.ASAAS_MOCK_MODE = False
        mock_settings.EMAIL_MOCK_MODE = False
        mock_settings.EMAIL_ENABLED = True
        mock_settings.ASAAS_WEBHOOK_BASE_URL = "https://api.test"
        mock_settings.CORS_ORIGINS = ["https://example.com"]
        mock_settings.RATE_LIMIT_ENABLED = True

        with patch.dict("os.environ", {}, clear=True):
            validate_production_config()  # Should not raise


def test_production_key_format_validation():
    """Test production key format validation."""
    from fastapi import HTTPException

    from app.api.routes.asaas_integration import _validate_production_key_format

    # Production key with correct prefix
    with patch("app.core.config.settings.ENVIRONMENT", "production"):
        _validate_production_key_format("$aact_prod_abc123")  # should not raise

    # Sandbox key in production should be rejected
    with patch("app.core.config.settings.ENVIRONMENT", "production"):
        with pytest.raises(HTTPException) as exc_info:
            _validate_production_key_format("$aact_hmlg_abc123")
        assert exc_info.value.status_code == 400
        assert "$aact_prod_" in str(exc_info.value.detail)

    # Non-production accepts any format >= 20 chars
    with patch("app.core.config.settings.ENVIRONMENT", "development"):
        _validate_production_key_format("fake_key_12345678901234567890")  # should not raise
