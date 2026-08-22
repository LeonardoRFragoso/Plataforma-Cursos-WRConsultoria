"""Tests for Asaas provider hardening: User-Agent, sanitized errors, webhook management."""

import pytest

from app.models.payment import PaymentMethod
from app.services.asaas_provider import _REQUIRED_WEBHOOK_EVENTS, AsaasProvider
from app.services.payment_provider_base import PaymentProviderError


@pytest.mark.asyncio
async def test_asaas_headers_include_user_agent():
    """Every Asaas request must include an explicit User-Agent."""
    provider = AsaasProvider(api_key="fake_key_12345678901234567890", mock=True)
    headers = provider._headers()

    assert "access_token" in headers
    assert headers["access_token"] == "fake_key_12345678901234567890"
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"
    assert "User-Agent" in headers
    assert "WR-Cursos" in headers["User-Agent"]
    # Authorization Bearer must NOT exist (Asaas uses access_token header)
    assert "Authorization" not in headers
    assert "Bearer" not in headers.get("Authorization", "")


@pytest.mark.asyncio
async def test_asaas_error_does_not_expose_raw_body():
    """PaymentProviderError must not include raw response body."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    # Simulate a 401 response
    from unittest import mock

    mock_response = mock.MagicMock()
    mock_response.status_code = 401
    mock_response.text = '{"errors":[{"code":"invalid_access_token","description":"secret_key_leaked"}]}'

    with mock.patch("httpx.AsyncClient.request", return_value=mock_response), \
         pytest.raises(PaymentProviderError) as exc_info:
        await provider._request("GET", "/v3/customers")

    # The error message must NOT contain the raw response body
    error_msg = str(exc_info.value)
    assert "secret_key_leaked" not in error_msg
    assert "invalid_access_token" not in error_msg
    # The safe message should be generic
    assert exc_info.value.safe_message == "Asaas authentication failed"
    assert exc_info.value.provider_error_code == "invalid_access_token"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_asaas_error_404_sanitized():
    """404 errors must be sanitized."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    from unittest import mock

    mock_response = mock.MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"errors":[{"code":"not_found","description":"payment pay_123 not found"}]}'

    with mock.patch("httpx.AsyncClient.request", return_value=mock_response), \
         pytest.raises(PaymentProviderError) as exc_info:
        await provider._request("GET", "/v3/payments/pay_123")

    error_msg = str(exc_info.value)
    assert "pay_123" not in error_msg
    assert "not found" not in error_msg.lower() or "Asaas resource not found" in error_msg


@pytest.mark.asyncio
async def test_asaas_webhook_create_mock():
    """create_webhook in mock mode returns a WebhookConfig."""
    provider = AsaasProvider(api_key="fake_key", mock=True)
    result = await provider.create_webhook(
        name="WR Cursos Payments - wr",
        url="https://api.test/webhook/wr",
        auth_token="x" * 43,  # 43 chars, valid
    )
    assert result.id.startswith("mock-wh-")
    assert result.enabled is True
    assert result.interrupted is False
    assert "PAYMENT_RECEIVED" in result.events


@pytest.mark.asyncio
async def test_asaas_webhook_token_too_short_rejected():
    """Webhook auth token must be 32-255 characters."""
    provider = AsaasProvider(api_key="fake_key", mock=True)
    with pytest.raises(PaymentProviderError) as exc_info:
        await provider.create_webhook(
            name="test",
            url="https://test.test/webhook",
            auth_token="short",  # too short
        )
    assert exc_info.value.provider_error_code == "invalid_token_length"


@pytest.mark.asyncio
async def test_asaas_reconcile_webhook_mock():
    """reconcile_webhook in mock mode creates a webhook (no existing)."""
    provider = AsaasProvider(api_key="fake_key", mock=True)
    result = await provider.reconcile_webhook(
        webhook_name="WR Cursos Payments - wr",
        webhook_url="https://api.test/webhook/wr",
        auth_token="x" * 43,
    )
    assert result.enabled is True
    assert result.id.startswith("mock-wh-")


@pytest.mark.asyncio
async def test_asaas_required_webhook_events_include_key_events():
    """Required webhook events must include all payment lifecycle events."""
    required = [
        "PAYMENT_CREATED",
        "PAYMENT_CONFIRMED",
        "PAYMENT_RECEIVED",
        "PAYMENT_OVERDUE",
        "PAYMENT_REFUNDED",
        "PAYMENT_CHARGEBACK_REQUESTED",
        "PAYMENT_CHARGEBACK_DISPUTE",
        "PAYMENT_AWAITING_CHARGEBACK_REVERSAL",
        "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
        "PAYMENT_AWAITING_RISK_ANALYSIS",
        "PAYMENT_APPROVED_BY_RISK_ANALYSIS",
        "PAYMENT_REPROVED_BY_RISK_ANALYSIS",
        "PAYMENT_AUTHORIZED",
        "PAYMENT_UPDATED",
    ]
    for event in required:
        assert event in _REQUIRED_WEBHOOK_EVENTS, f"Missing required event: {event}"


@pytest.mark.asyncio
async def test_asaas_create_checkout_uses_payment_id_as_external_reference():
    """create_checkout must set externalReference to str(payment_id), not enrollment_id."""
    import uuid
    provider = AsaasProvider(api_key="fake_key", mock=True)
    payment_id = uuid.uuid4()
    enrollment_id = uuid.uuid4()

    result = await provider.create_checkout(
        payment_id=payment_id,
        amount=100.0,
        student_email="test@test.com",
        student_name="Test",
        course_name="Test Course",
        method=PaymentMethod.PIX,
        enrollment_id=enrollment_id,
    )

    # The mock checkout stores externalReference in raw
    assert result.raw["externalReference"] == str(payment_id)
    assert result.raw["externalReference"] != str(enrollment_id)
