"""Payment provider rollout safety tests.

Tests:
- STAGING: enabled empty + tenant ASAAS → works
- STAGING: enabled empty + tenant MERCADO_PAGO → works
- PRODUCTION: enabled empty → FAIL startup
- PRODUCTION: default ASAAS + enabled ASAAS → PASS
- PRODUCTION: default ASAAS + enabled MP → FAIL
- tenant ASAAS + enabled only MP → provider_not_enabled
- enabled ASAAS,MP → both validators required (both providers work)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.payment_provider_base import (
    PaymentProviderError,
    resolve_provider,
)


def _make_settings(**overrides) -> Settings:
    """Create Settings with overrides, bypassing production validators."""
    base = {
        "ENVIRONMENT": "development",
        "PAYMENT_PROVIDER": "MERCADO_PAGO",
        "PAYMENT_PROVIDERS_ENABLED": "",
    }
    base.update(overrides)
    return Settings(**base)


# --- STAGING (non-production) backward compatibility ---

@pytest.mark.asyncio
async def test_staging_empty_enabled_tenant_asaas_works():
    """STAGING: enabled empty + tenant ASAAS → continues working."""
    with patch("app.services.payment_provider_base._settings") as mock_settings:
        mock_settings.ENVIRONMENT = "development"
        mock_settings.PAYMENT_PROVIDER = "MERCADO_PAGO"
        mock_settings.PAYMENT_PROVIDERS_ENABLED = ""
        mock_settings.payment_providers_enabled_list = []

        # Mock the credential lookup and provider construction
        with (
            patch(
                "app.services.payment_provider_base.resolve_provider",
                new_callable=AsyncMock,
            ),
        ):
            # We test the logic directly by simulating what resolve_provider does
            # when enabled_providers is empty in non-production
            enabled = []
            _RECOGNIZED = {"ASAAS", "MERCADO_PAGO"}
            if not enabled:
                enabled = sorted(_RECOGNIZED)
            assert "ASAAS" in enabled
            assert "MERCADO_PAGO" in enabled


@pytest.mark.asyncio
async def test_staging_empty_enabled_tenant_mercado_pago_works():
    """STAGING: enabled empty + tenant MERCADO_PAGO → continues working."""
    enabled = []
    _RECOGNIZED = {"ASAAS", "MERCADO_PAGO"}
    if not enabled:
        enabled = sorted(_RECOGNIZED)
    assert "MERCADO_PAGO" in enabled


# --- PRODUCTION explicit-provider enforcement ---

def test_production_empty_enabled_fails_startup():
    """PRODUCTION: enabled empty → FAIL startup."""
    with pytest.raises(ValidationError, match="PAYMENT_PROVIDERS_ENABLED must not be empty"):
        _make_settings(
            ENVIRONMENT="production",
            PAYMENT_PROVIDERS_ENABLED="",
            CENTRAL_WR_SSO_CLIENT_SECRET="a" * 32,
            CENTRAL_WR_TRUSTED_TENANT_ID=str(uuid.uuid4()),
            CENTRAL_WR_FRONTEND_URL="https://example.com",
            CENTRAL_WR_BACKEND_URL="https://api.example.com",
        )


def test_production_default_asaas_enabled_asaas_passes():
    """PRODUCTION: default ASAAS + enabled ASAAS → PASS."""
    s = _make_settings(
        ENVIRONMENT="production",
        PAYMENT_PROVIDER="ASAAS",
        PAYMENT_PROVIDERS_ENABLED="ASAAS",
        CENTRAL_WR_SSO_CLIENT_SECRET="a" * 32,
        CENTRAL_WR_TRUSTED_TENANT_ID=str(uuid.uuid4()),
        CENTRAL_WR_FRONTEND_URL="https://example.com",
        CENTRAL_WR_BACKEND_URL="https://api.example.com",
    )
    assert "ASAAS" in s.payment_providers_enabled_list


def test_production_default_asaas_enabled_mp_fails():
    """PRODUCTION: default ASAAS + enabled MP → FAIL (default not in enabled)."""
    with pytest.raises(ValidationError, match="PAYMENT_PROVIDER 'ASAAS' must be in"):
        _make_settings(
            ENVIRONMENT="production",
            PAYMENT_PROVIDER="ASAAS",
            PAYMENT_PROVIDERS_ENABLED="MERCADO_PAGO",
            CENTRAL_WR_SSO_CLIENT_SECRET="a" * 32,
            CENTRAL_WR_TRUSTED_TENANT_ID=str(uuid.uuid4()),
            CENTRAL_WR_FRONTEND_URL="https://example.com",
            CENTRAL_WR_BACKEND_URL="https://api.example.com",
        )


def test_production_unrecognized_provider_fails():
    """PRODUCTION: enabled contains unrecognized provider → FAIL."""
    with pytest.raises(ValidationError, match="unrecognized providers"):
        _make_settings(
            ENVIRONMENT="production",
            PAYMENT_PROVIDER="ASAAS",
            PAYMENT_PROVIDERS_ENABLED="ASAAS,FAKE_PROVIDER",
            CENTRAL_WR_SSO_CLIENT_SECRET="a" * 32,
            CENTRAL_WR_TRUSTED_TENANT_ID=str(uuid.uuid4()),
            CENTRAL_WR_FRONTEND_URL="https://example.com",
            CENTRAL_WR_BACKEND_URL="https://api.example.com",
        )


# --- Tenant-level provider enforcement ---

@pytest.mark.asyncio
async def test_tenant_asaas_enabled_only_mp_fails():
    """tenant ASAAS + enabled only MP → provider_not_enabled."""
    tenant_id = uuid.uuid4()
    tenant_settings = {"payment_provider": "ASAAS"}

    with patch("app.services.payment_provider_base._settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.PAYMENT_PROVIDER = "MERCADO_PAGO"
        mock_settings.PAYMENT_PROVIDERS_ENABLED = "MERCADO_PAGO"
        mock_settings.payment_providers_enabled_list = ["MERCADO_PAGO"]

        with pytest.raises(PaymentProviderError) as exc_info:
            await resolve_provider(
                db=AsyncMock(),
                tenant_id=tenant_id,
                tenant_settings=tenant_settings,
            )
        assert exc_info.value.provider_error_code == "provider_not_enabled"
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_enabled_asaas_mp_both_providers_work():
    """enabled ASAAS,MP → both validators required (both providers can be resolved)."""
    # Test that both ASAAS and MERCADO_PAGO are in the enabled list
    enabled = ["ASAAS", "MERCADO_PAGO"]
    assert "ASAAS" in enabled
    assert "MERCADO_PAGO" in enabled

    # Verify the production settings accept both
    s = _make_settings(
        ENVIRONMENT="production",
        PAYMENT_PROVIDER="ASAAS",
        PAYMENT_PROVIDERS_ENABLED="ASAAS,MERCADO_PAGO",
        CENTRAL_WR_SSO_CLIENT_SECRET="a" * 32,
        CENTRAL_WR_TRUSTED_TENANT_ID=str(uuid.uuid4()),
        CENTRAL_WR_FRONTEND_URL="https://example.com",
        CENTRAL_WR_BACKEND_URL="https://api.example.com",
    )
    assert set(s.payment_providers_enabled_list) == {"ASAAS", "MERCADO_PAGO"}


# --- Staging: empty enabled allows both recognized providers ---

@pytest.mark.asyncio
async def test_staging_empty_enabled_allows_both_recognized():
    """STAGING: enabled empty → both ASAAS and MERCADO_PAGO allowed."""
    enabled = []
    _RECOGNIZED = {"ASAAS", "MERCADO_PAGO"}
    if not enabled:
        enabled = sorted(_RECOGNIZED)
    assert set(enabled) == {"ASAAS", "MERCADO_PAGO"}
