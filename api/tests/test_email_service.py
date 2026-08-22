"""Tests for the email service."""

import pytest

from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_mock_mode_logs_email():
    """In mock mode, emails are logged but not sent."""
    service = EmailService(mock=True)
    result = await service.send_email(
        to="test@example.com",
        subject="Test Subject",
        html_body="<p>Hello</p>",
        text_body="Hello",
    )
    assert result is True
    assert len(service.sent_emails) == 1
    assert service.sent_emails[0]["to"] == "test@example.com"
    assert service.sent_emails[0]["subject"] == "Test Subject"
    assert service.sent_emails[0]["mock"] is True


@pytest.mark.asyncio
async def test_mock_password_reset():
    """Mock password reset email is recorded."""
    service = EmailService(mock=True)
    result = await service.send_password_reset(
        to="user@test.com",
        reset_token="abc123",
        frontend_url="https://app.test",
        tenant_name="Test Platform",
    )
    assert result is True
    assert len(service.sent_emails) == 1
    email = service.sent_emails[0]
    assert "reset-password?token=abc123" in email["html_body"]
    assert "Test Platform" in email["subject"]


@pytest.mark.asyncio
async def test_mock_account_activation():
    """Mock account activation email is recorded."""
    service = EmailService(mock=True)
    result = await service.send_account_activation(
        to="newuser@test.com",
        activation_token="xyz789",
        frontend_url="https://app.test",
        tenant_name="Test Platform",
    )
    assert result is True
    assert len(service.sent_emails) == 1
    email = service.sent_emails[0]
    assert "activate?token=xyz789" in email["html_body"]
    assert "Test Platform" in email["subject"]


@pytest.mark.asyncio
async def test_no_smtp_configured_returns_false():
    """Without SMTP credentials, email is not sent and returns False."""
    service = EmailService(
        smtp_user="",
        smtp_password="",
        mock=False,
    )
    result = await service.send_email(
        to="test@example.com",
        subject="Test",
        html_body="<p>Hello</p>",
    )
    assert result is False
    assert len(service.sent_emails) == 0


def test_get_email_service_singleton():
    """get_email_service returns a singleton."""
    from app.services.email_service import get_email_service, reset_email_service

    reset_email_service()
    s1 = get_email_service()
    s2 = get_email_service()
    assert s1 is s2
    reset_email_service()
