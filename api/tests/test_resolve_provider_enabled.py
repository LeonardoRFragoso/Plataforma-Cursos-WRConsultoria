"""Tests for resolve_provider fail-closed behavior with PAYMENT_PROVIDERS_ENABLED.

Verifies that:
1. Global ASAAS + enabled ASAAS + tenant ASAAS → OK
2. Global MP + enabled MP + tenant MP → OK
3. Global MP + enabled MP + tenant ASAAS → REJECT (provider not enabled)
4. Global ASAAS + enabled ASAAS + tenant MP → REJECT (provider not enabled)
5. Multi-provider enabled → both providers selectable by tenant
6. Tenant provider not in enabled list → fail closed, no silent fallback
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.payment_provider_base import PaymentProviderError, resolve_provider


@pytest.fixture
def mock_tenant_settings():
    """Return a mutable dict for tenant settings."""
    return {}


class TestResolveProviderEnabled:
    """Test that resolve_provider respects PAYMENT_PROVIDERS_ENABLED."""

    @pytest.mark.asyncio
    async def test_global_asaas_enabled_asaas_tenant_asaas_ok(self, mock_tenant_settings):
        """Global ASAAS + enabled ASAAS + tenant ASAAS → OK."""
        mock_tenant_settings["payment_provider"] = "ASAAS"
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "ASAAS"
            mock_s.payment_providers_enabled_list = ["ASAAS"]
            with patch("app.services.asaas_provider.AsaasProvider") as mock_provider_cls:
                with patch(
                    "app.services.tenant_secret_service.get_asaas_api_key",
                    new_callable=AsyncMock,
                    return_value="fake_key",
                ):
                    mock_provider_cls.return_value = AsyncMock()
                    result = await resolve_provider(
                        db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                    )
                    assert result is not None

    @pytest.mark.asyncio
    async def test_global_mp_enabled_mp_tenant_mp_ok(self, mock_tenant_settings):
        """Global MP + enabled MP + tenant MP → OK."""
        mock_tenant_settings["payment_provider"] = "MERCADO_PAGO"
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "MERCADO_PAGO"
            mock_s.payment_providers_enabled_list = ["MERCADO_PAGO"]
            with patch("app.services.mercado_pago_provider.MercadoPagoProvider") as mock_provider_cls:
                with patch(
                    "app.services.tenant_secret_service.get_mercado_pago_access_token",
                    new_callable=AsyncMock,
                    return_value="fake_token",
                ):
                    mock_provider_cls.return_value = AsyncMock()
                    result = await resolve_provider(
                        db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                    )
                    assert result is not None

    @pytest.mark.asyncio
    async def test_global_mp_enabled_mp_tenant_asaas_rejected(self, mock_tenant_settings):
        """Global MP + enabled MP + tenant ASAAS → REJECT."""
        mock_tenant_settings["payment_provider"] = "ASAAS"
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "MERCADO_PAGO"
            mock_s.payment_providers_enabled_list = ["MERCADO_PAGO"]
            with pytest.raises(PaymentProviderError) as exc_info:
                await resolve_provider(
                    db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                )
            assert exc_info.value.status_code == 403
            assert "not enabled" in str(exc_info.value).lower()
            assert exc_info.value.provider_error_code == "provider_not_enabled"

    @pytest.mark.asyncio
    async def test_global_asaas_enabled_asaas_tenant_mp_rejected(self, mock_tenant_settings):
        """Global ASAAS + enabled ASAAS + tenant MP → REJECT."""
        mock_tenant_settings["payment_provider"] = "MERCADO_PAGO"
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "ASAAS"
            mock_s.payment_providers_enabled_list = ["ASAAS"]
            with pytest.raises(PaymentProviderError) as exc_info:
                await resolve_provider(
                    db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                )
            assert exc_info.value.status_code == 403
            assert "not enabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_multi_provider_both_selectable(self, mock_tenant_settings):
        """Multi-provider enabled → both providers selectable by tenant."""
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "ASAAS"
            mock_s.payment_providers_enabled_list = ["ASAAS", "MERCADO_PAGO"]

            # Tenant selects ASAAS
            mock_tenant_settings["payment_provider"] = "ASAAS"
            with patch("app.services.asaas_provider.AsaasProvider") as mock_asaas:
                with patch(
                    "app.services.tenant_secret_service.get_asaas_api_key",
                    new_callable=AsyncMock,
                    return_value="fake_key",
                ):
                    mock_asaas.return_value = AsyncMock()
                    result = await resolve_provider(
                        db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                    )
                    assert result is not None

            # Tenant selects MERCADO_PAGO
            mock_tenant_settings["payment_provider"] = "MERCADO_PAGO"
            with patch("app.services.mercado_pago_provider.MercadoPagoProvider") as mock_mp:
                with patch(
                    "app.services.tenant_secret_service.get_mercado_pago_access_token",
                    new_callable=AsyncMock,
                    return_value="fake_token",
                ):
                    mock_mp.return_value = AsyncMock()
                    result = await resolve_provider(
                        db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                    )
                    assert result is not None

    @pytest.mark.asyncio
    async def test_tenant_provider_not_in_enabled_no_silent_fallback(self, mock_tenant_settings):
        """Tenant selects provider not enabled → fail closed, no silent fallback."""
        mock_tenant_settings["payment_provider"] = "ASAAS"
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "MERCADO_PAGO"
            mock_s.payment_providers_enabled_list = ["MERCADO_PAGO"]
            # Must NOT fall back to MERCADO_PAGO — must raise
            with pytest.raises(PaymentProviderError) as exc_info:
                await resolve_provider(
                    db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                )
            assert exc_info.value.status_code == 403
            # Verify it did NOT silently use Mercado Pago
            assert "not enabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_no_tenant_provider_uses_global_if_enabled(self, mock_tenant_settings):
        """No tenant override → uses global default (must be enabled)."""
        # tenant_settings has no "payment_provider" key
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "MERCADO_PAGO"
            mock_s.payment_providers_enabled_list = ["MERCADO_PAGO"]
            with patch("app.services.mercado_pago_provider.MercadoPagoProvider") as mock_mp:
                with patch(
                    "app.services.tenant_secret_service.get_mercado_pago_access_token",
                    new_callable=AsyncMock,
                    return_value="fake_token",
                ):
                    mock_mp.return_value = AsyncMock()
                    result = await resolve_provider(
                        db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                    )
                    assert result is not None

    @pytest.mark.asyncio
    async def test_no_tenant_provider_global_not_enabled_rejected(self, mock_tenant_settings):
        """No tenant override + global default not in enabled list → REJECT."""
        with patch("app.services.payment_provider_base._settings") as mock_s:
            mock_s.PAYMENT_PROVIDER = "MERCADO_PAGO"
            mock_s.payment_providers_enabled_list = ["ASAAS"]
            with pytest.raises(PaymentProviderError) as exc_info:
                await resolve_provider(
                    db=AsyncMock(), tenant_id="test-tenant", tenant_settings=mock_tenant_settings
                )
            assert exc_info.value.status_code == 403
