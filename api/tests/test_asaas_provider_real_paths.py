"""Tests for Asaas provider non-mock API paths (using httpx mocking)."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.payment import PaymentMethod
from app.services.asaas_provider import AsaasProvider
from app.services.payment_provider_base import PaymentProviderError


@pytest.mark.asyncio
async def test_asaas_create_customer_real_path():
    """create_or_update_customer calls the API and returns CustomerResult."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "cus_test_123",
        "name": "Test Customer",
        "email": "test@test.com",
        "cpfCnpj": "12345678901",
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.create_or_update_customer(
            name="Test Customer",
            email="test@test.com",
            cpf_cnpj="12345678901",
            phone="11999999999",
            external_id="stu-123",
        )

    assert result.provider_customer_id == "cus_test_123"


@pytest.mark.asyncio
async def test_asaas_create_checkout_real_path():
    """create_checkout calls the API and returns CheckoutResult."""
    import uuid
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "pay_test_123",
        "invoiceUrl": "https://asaas.com/checkout/123",
        "status": "PENDING",
        "value": 100.0,
        "billingType": "PIX",
    }
    mock_response.text = "{}"

    payment_id = uuid.uuid4()
    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.create_checkout(
            payment_id=payment_id,
            amount=100.0,
            student_email="test@test.com",
            student_name="Test",
            course_name="Test Course",
            method=PaymentMethod.PIX,
            customer_id="cus_test_123",
        )

    assert result.provider_payment_id == "pay_test_123"
    assert result.checkout_url == "https://asaas.com/checkout/123"


@pytest.mark.asyncio
async def test_asaas_get_payment_info_real_path():
    """get_payment_info calls the API and returns PaymentInfoResult."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "pay_test_123",
        "status": "RECEIVED",
        "value": 100.0,
        "billingType": "PIX",
        "customer": "cus_test_123",
        "externalReference": "test-payment-id",
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.get_payment_info("pay_test_123")

    assert result.provider_payment_id == "pay_test_123"
    assert result.status == "RECEIVED"
    assert result.amount == 100.0
    assert result.billing_type == "PIX"
    assert result.customer_id == "cus_test_123"
    assert result.external_reference == "test-payment-id"


@pytest.mark.asyncio
async def test_asaas_list_webhooks_real_path():
    """list_webhooks calls the API and returns list."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "wh_1",
                "name": "Test Webhook",
                "url": "https://test.com/webhook",
                "enabled": True,
                "interrupted": False,
                "event": {
                    "paymentCreated": True,
                    "paymentConfirmed": True,
                    "paymentReceived": True,
                },
            }
        ],
        "totalCount": 1,
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.list_webhooks()

    assert result.mock is False
    assert len(result.data) == 1
    assert result.data[0]["id"] == "wh_1"
    assert result.data[0]["enabled"] is True
    assert result.data[0]["interrupted"] is False


@pytest.mark.asyncio
async def test_asaas_create_webhook_real_path():
    """create_webhook calls the API and returns WebhookConfig."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "wh_new_123",
        "name": "WR Cursos Payments - wr",
        "url": "https://api.test/webhook/wr",
        "enabled": True,
        "interrupted": False,
        "event": {
            "paymentCreated": True,
            "paymentConfirmed": True,
            "paymentReceived": True,
        },
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.create_webhook(
            name="WR Cursos Payments - wr",
            url="https://api.test/webhook/wr",
            auth_token="x" * 43,
        )

    assert result.id == "wh_new_123"
    assert result.enabled is True
    assert result.interrupted is False


@pytest.mark.asyncio
async def test_asaas_delete_webhook_real_path():
    """delete_webhook calls the API and returns True."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"deleted": True}
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.delete_webhook("wh_test_123")

    assert result is True


@pytest.mark.asyncio
async def test_asaas_get_webhook_real_path():
    """get_webhook calls the API and returns WebhookConfig."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "wh_get_123",
        "name": "Test",
        "url": "https://test.com/webhook",
        "enabled": True,
        "interrupted": False,
        "event": {"paymentReceived": True},
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        result = await provider.get_webhook("wh_get_123")

    assert result.id == "wh_get_123"
    assert result.enabled is True


@pytest.mark.asyncio
async def test_asaas_update_webhook_real_path():
    """update_webhook calls PUT /v3/webhooks/{id} (NOT POST) and returns WebhookConfig."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "wh_upd_123",
        "name": "Updated",
        "url": "https://test.com/webhook",
        "enabled": True,
        "interrupted": False,
        "event": {"paymentReceived": True},
    }
    mock_response.text = "{}"

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        result = await provider.update_webhook(
            webhook_id="wh_upd_123",
            name="Updated",
            url="https://test.com/webhook",
            auth_token="x" * 43,
            enabled=True,
        )

    assert result.id == "wh_upd_123"
    assert result.enabled is True

    # P0 regression: update_webhook MUST use PUT, not POST
    call_args = mock_req.call_args
    assert call_args.kwargs.get("method") == "PUT" or call_args.args[0] == "PUT"
    url = call_args.kwargs.get("url", "") or (call_args.args[1] if len(call_args.args) > 1 else "")
    assert "/v3/webhooks/wh_upd_123" in url


@pytest.mark.asyncio
async def test_asaas_request_500_raises_sanitized_error():
    """500 errors raise PaymentProviderError with safe message."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"errors":[{"code":"internal","description":"db connection lost"}]}'

    with patch("httpx.AsyncClient.request", return_value=mock_response), \
         pytest.raises(PaymentProviderError) as exc_info:
        await provider._request("GET", "/v3/customers")

    assert exc_info.value.status_code == 500
    assert "db connection lost" not in str(exc_info.value)
    assert exc_info.value.safe_message == "Asaas request failed with status 500"


@pytest.mark.asyncio
async def test_asaas_request_400_raises_sanitized_error():
    """400 errors raise PaymentProviderError with safe message."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"errors":[{"code":"invalid","description":"invalid cpf"}]}'

    with patch("httpx.AsyncClient.request", return_value=mock_response), \
         pytest.raises(PaymentProviderError) as exc_info:
        await provider._request("POST", "/v3/customers")

    assert exc_info.value.status_code == 400
    assert "invalid cpf" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_asaas_request_network_error_raises_sanitized():
    """Network errors raise PaymentProviderError with safe message."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    import httpx
    with patch("httpx.AsyncClient.request", side_effect=httpx.ConnectError("connection refused")), \
         pytest.raises(PaymentProviderError) as exc_info:
        await provider._request("GET", "/v3/customers")

    assert "connection refused" not in str(exc_info.value)
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_reconcile_webhook_existing_uses_put():
    """reconcile_webhook uses PUT to update an existing webhook (not POST)."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    # list_webhooks returns one matching webhook
    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {
        "data": [
            {
                "id": "wh_existing_123",
                "name": "WR Cursos Payments - wr",
                "url": "https://old.test/webhook",
                "enabled": False,
                "interrupted": True,
                "event": {"paymentReceived": False},
            }
        ],
        "totalCount": 1,
    }
    list_response.text = "{}"

    # update response
    update_response = MagicMock()
    update_response.status_code = 200
    update_response.json.return_value = {
        "id": "wh_existing_123",
        "name": "WR Cursos Payments - wr",
        "url": "https://new.test/webhook",
        "enabled": True,
        "interrupted": False,
        "event": {"paymentReceived": True},
    }
    update_response.text = "{}"

    call_count = [0]

    def mock_request_side_effect(*args, **kwargs):
        call_count[0] += 1
        # First call is list_webhooks (GET /v3/webhooks)
        if call_count[0] == 1:
            return list_response
        # Second call is update_webhook (must be PUT)
        return update_response

    with patch("httpx.AsyncClient.request", side_effect=mock_request_side_effect) as mock_req:
        result = await provider.reconcile_webhook(
            webhook_name="WR Cursos Payments - wr",
            webhook_url="https://new.test/webhook",
            auth_token="x" * 43,
        )

    assert result.id == "wh_existing_123"
    assert result.enabled is True

    # Verify the second call (update) used PUT, not POST
    calls = mock_req.call_args_list
    assert len(calls) == 2
    update_call = calls[1]
    update_method = update_call.kwargs.get("method") or (update_call.args[0] if update_call.args else None)
    assert update_method == "PUT", f"reconcile_webhook update must use PUT, got {update_method}"
    update_url = update_call.kwargs.get("url", "") or (update_call.args[1] if len(update_call.args) > 1 else "")
    assert "/v3/webhooks/wh_existing_123" in update_url


@pytest.mark.asyncio
async def test_reconcile_webhook_new_uses_post():
    """reconcile_webhook uses POST to create a new webhook when none exists."""
    provider = AsaasProvider(api_key="fake_key", mock=False, sandbox=True)

    # list_webhooks returns empty
    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = {"data": [], "totalCount": 0}
    list_response.text = "{}"

    # create response
    create_response = MagicMock()
    create_response.status_code = 200
    create_response.json.return_value = {
        "id": "wh_new_456",
        "name": "WR Cursos Payments - wr",
        "url": "https://new.test/webhook",
        "enabled": True,
        "interrupted": False,
        "event": {"paymentReceived": True},
    }
    create_response.text = "{}"

    call_count = [0]

    def mock_request_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return list_response
        return create_response

    with patch("httpx.AsyncClient.request", side_effect=mock_request_side_effect) as mock_req:
        result = await provider.reconcile_webhook(
            webhook_name="WR Cursos Payments - wr",
            webhook_url="https://new.test/webhook",
            auth_token="x" * 43,
        )

    assert result.id == "wh_new_456"
    assert result.enabled is True

    # Verify the second call (create) used POST
    calls = mock_req.call_args_list
    assert len(calls) == 2
    create_call = calls[1]
    create_method = create_call.kwargs.get("method") or (create_call.args[0] if create_call.args else None)
    assert create_method == "POST", f"reconcile_webhook create must use POST, got {create_method}"
    create_url = create_call.kwargs.get("url", "") or (create_call.args[1] if len(create_call.args) > 1 else "")
    assert create_url.endswith("/v3/webhooks")
