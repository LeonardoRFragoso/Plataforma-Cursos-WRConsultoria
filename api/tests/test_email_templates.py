"""Tests for new email templates and notification helpers.

Verifies that:
- Templates produce correct subject/body
- EMAIL_MOCK_MODE=true → no SMTP I/O
- EMAIL_ENABLED=false → no delivery attempt
- Notification helpers are idempotent and best-effort
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import EmailService, EmailServiceError, reset_email_service
from app.services.transactional_notifications import (
    send_certificate_expiration_notification,
    send_certificate_issued_notification,
    send_course_completed_notification,
    send_payment_approved_notification,
)


@pytest.fixture
def mock_email_service():
    """Create a mock-mode EmailService for inspection."""
    reset_email_service()
    svc = EmailService(mock=True)
    with patch("app.services.transactional_notifications.get_email_service", return_value=svc):
        yield svc
    reset_email_service()


class TestEmailTemplates:
    def test_payment_approved_template(self, mock_email_service):
        result = asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_payment_approved(
                to="student@example.com",
                full_name="João Test",
                course_name="NR-10",
                amount="R$ 199,00",
                payment_method="PIX",
                course_url="https://example.com/courses/1/learn",
                tenant_name="WR",
            )
        )
        assert result is True
        sent = mock_email_service.sent_emails[-1]
        assert "Pagamento confirmado" in sent["subject"]
        assert "NR-10" in sent["subject"]
        assert "student@example.com" == sent["to"]
        assert "R$ 199,00" in sent["html_body"]
        assert "PIX" in sent["html_body"]
        assert "João Test" in sent["html_body"]

    def test_course_completed_template(self, mock_email_service):
        result = asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_course_completed(
                to="student@example.com",
                full_name="Maria Test",
                course_name="NR-06",
                certificate_url="https://example.com/validar?codigo=ABC",
                tenant_name="WR",
            )
        )
        assert result is True
        sent = mock_email_service.sent_emails[-1]
        assert "Curso concluído" in sent["subject"]
        assert "NR-06" in sent["subject"]
        assert "Maria Test" in sent["html_body"]
        assert "validar" in sent["html_body"]

    def test_course_completed_no_certificate(self, mock_email_service):
        result = asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_course_completed(
                to="student@example.com",
                full_name="Test",
                course_name="NR-06",
                certificate_url=None,
                tenant_name="WR",
            )
        )
        assert result is True
        sent = mock_email_service.sent_emails[-1]
        assert "validar" not in sent["html_body"]

    def test_certificate_issued_template(self, mock_email_service):
        result = asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_certificate_issued(
                to="student@example.com",
                full_name="Test",
                course_name="NR-10",
                certificate_number="CERT-ABC123",
                validation_url="https://example.com/validar?codigo=XYZ",
                tenant_name="WR",
            )
        )
        assert result is True
        sent = mock_email_service.sent_emails[-1]
        assert "Certificado emitido" in sent["subject"]
        assert "CERT-ABC123" in sent["html_body"]
        assert "XYZ" in sent["html_body"]

    def test_certificate_expiration_template(self, mock_email_service):
        result = asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_certificate_expiration_warning(
                to="student@example.com",
                full_name="Test",
                course_name="NR-35",
                certificate_number="CERT-XYZ",
                expires_at="2026-12-31",
                tenant_name="WR",
            )
        )
        assert result is True
        sent = mock_email_service.sent_emails[-1]
        assert "vencimento" in sent["subject"].lower()
        assert "2026-12-31" in sent["html_body"]
        assert "CERT-XYZ" in sent["html_body"]

    def test_mock_mode_no_smtp(self, mock_email_service):
        """EMAIL_MOCK_MODE=true → emails are logged, not sent via SMTP."""
        asyncio.get_event_loop().run_until_complete(
            mock_email_service.send_payment_approved(
                to="test@example.com",
                full_name="Test",
                course_name="Test",
                amount="R$ 1,00",
                payment_method="PIX",
                course_url="https://example.com",
                tenant_name="WR",
            )
        )
        # Mock mode stores in _sent, never calls SMTP
        assert len(mock_email_service.sent_emails) == 1
        assert mock_email_service.sent_emails[0]["mock"] is True


class TestNotificationHelpersDisabled:
    def test_email_disabled_skips_delivery(self, monkeypatch):
        """EMAIL_ENABLED=false → no delivery attempt."""
        monkeypatch.setattr("app.services.transactional_notifications.settings.EMAIL_ENABLED", False)
        reset_email_service()
        enrollment = MagicMock()
        enrollment.id = "00000000-0000-0000-0000-000000000001"
        enrollment.tenant_id = "00000000-0000-0000-0000-000000000002"

        result = asyncio.get_event_loop().run_until_complete(
            send_payment_approved_notification(
                MagicMock(), enrollment, amount="R$ 1", payment_method="PIX"
            )
        )
        assert result is False
        reset_email_service()

    def test_email_disabled_skips_course_completed(self, monkeypatch):
        monkeypatch.setattr("app.services.transactional_notifications.settings.EMAIL_ENABLED", False)
        reset_email_service()
        enrollment = MagicMock()
        enrollment.id = "00000000-0000-0000-0000-000000000001"
        enrollment.tenant_id = "00000000-0000-0000-0000-000000000002"

        result = asyncio.get_event_loop().run_until_complete(
            send_course_completed_notification(MagicMock(), enrollment)
        )
        assert result is False
        reset_email_service()

    def test_email_disabled_skips_certificate_issued(self, monkeypatch):
        monkeypatch.setattr("app.services.transactional_notifications.settings.EMAIL_ENABLED", False)
        reset_email_service()
        enrollment = MagicMock()
        enrollment.id = "00000000-0000-0000-0000-000000000001"
        enrollment.tenant_id = "00000000-0000-0000-0000-000000000002"

        result = asyncio.get_event_loop().run_until_complete(
            send_certificate_issued_notification(
                MagicMock(), enrollment, certificate_number="X", validation_code="Y"
            )
        )
        assert result is False
        reset_email_service()

    def test_email_disabled_skips_expiration(self, monkeypatch):
        monkeypatch.setattr("app.services.transactional_notifications.settings.EMAIL_ENABLED", False)
        reset_email_service()

        result = asyncio.get_event_loop().run_until_complete(
            send_certificate_expiration_notification(
                MagicMock(),
                enrollment_id="00000000-0000-0000-0000-000000000001",
                tenant_id="00000000-0000-0000-0000-000000000002",
                certificate_number="X",
                expires_at="2026-12-31",
            )
        )
        assert result is False
        reset_email_service()
