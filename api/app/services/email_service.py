"""Email delivery service.

Sends transactional emails via SMTP (password reset, account activation,
B2C welcome and course-access notifications).
Tenant-aware: uses tenant branding/name in the email template.

Requirements:
- Tenant-aware frontend link (uses caller-resolved frontend URL)
- Tenant-aware branding/name
- HTML + text fallback
- SMTP timeout
- Sanitized exceptions (no credentials in logs)
- Production tokens never returned through HTTP
- Automated tests mock email sending (EMAIL_MOCK_MODE=true)
- CI sends no real email (EMAIL_MOCK_MODE defaults to true)
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Sanitized email error — never contains SMTP credentials."""


def _safe_header_text(value: str) -> str:
    """Collapse control characters before using database text in mail headers."""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


class EmailService:
    """SMTP-based email service with mock mode for tests/CI."""

    def __init__(
        self,
        smtp_server: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        mock: bool | None = None,
    ) -> None:
        self._smtp_server = smtp_server or settings.SMTP_SERVER
        self._smtp_port = smtp_port or settings.SMTP_PORT
        self._smtp_user = smtp_user or settings.SMTP_USER
        self._smtp_password = smtp_password or settings.SMTP_PASSWORD
        self._mock = mock if mock is not None else getattr(settings, "EMAIL_MOCK_MODE", True)
        self._sent: list[dict[str, Any]] = []  # For test inspection

    def _send_smtp_message(self, to: str, message: str) -> None:
        """Blocking SMTP operation, executed outside the asyncio event loop."""
        with smtplib.SMTP(self._smtp_server, self._smtp_port, timeout=30) as server:
            server.starttls()
            server.login(self._smtp_user, self._smtp_password)
            server.sendmail(self._smtp_user, [to], message)

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        from_name: str | None = None,
    ) -> bool:
        """Send an email. Returns True if sent (or mocked).

        Raises EmailServiceError on SMTP failure (sanitized — no
        credentials in the error message). Real SMTP I/O runs in a worker
        thread so a slow provider does not block the FastAPI event loop.
        """
        safe_subject = _safe_header_text(subject)
        safe_from_name = _safe_header_text(from_name or "Plataforma")

        if self._mock:
            self._sent.append({
                "to": to,
                "subject": safe_subject,
                "html_body": html_body,
                "text_body": text_body,
                "mock": True,
            })
            logger.info("Email mock sent to %s: %s", to, safe_subject)
            return True

        if not self._smtp_user or not self._smtp_password:
            logger.warning("SMTP not configured — email to %s not sent", to)
            return False

        from_addr = f"{safe_from_name} <{self._smtp_user}>"
        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = safe_subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            await asyncio.to_thread(self._send_smtp_message, to, msg.as_string())
            logger.info("Email sent to %s: %s", to, safe_subject)
            return True
        except smtplib.SMTPException as exc:
            # Sanitize: never include credentials in the error
            raise EmailServiceError(f"Failed to send email to {to}") from exc
        except Exception as exc:
            raise EmailServiceError(f"Failed to send email to {to}") from exc

    async def send_password_reset(
        self,
        *,
        to: str,
        reset_token: str,
        frontend_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Send a password reset email with a tenant-aware link."""
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        subject = f"Redefinição de senha — {tenant_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{escape(tenant_name)}</h2>
            <p>Você solicitou a redefinição de sua senha.</p>
            <p>Clique no link abaixo para redefinir sua senha:</p>
            <p><a href="{escape(reset_link, quote=True)}" style="display: inline-block; padding: 10px 20px; background: #4f46e5; color: white; text-decoration: none; border-radius: 5px;">Redefinir senha</a></p>
            <p>Se você não solicitou esta redefinição, ignore este email.</p>
            <p style="color: #999; font-size: 12px;">Este link expira em 1 hora.</p>
        </body>
        </html>
        """
        text = f"""
{tenant_name}

Você solicitou a redefinição de sua senha.
Acesse o link para redefinir: {reset_link}

Se você não solicitou esta redefinição, ignore este email.
Este link expira em 1 hora.
        """
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    async def send_account_activation(
        self,
        *,
        to: str,
        activation_token: str,
        frontend_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Send an account activation email with a tenant-aware link."""
        activation_link = f"{frontend_url}/activate?token={activation_token}"
        subject = f"Ative sua conta — {tenant_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{escape(tenant_name)}</h2>
            <p>Bem-vindo! Sua conta foi criada.</p>
            <p>Clique no link abaixo para ativar sua conta:</p>
            <p><a href="{escape(activation_link, quote=True)}" style="display: inline-block; padding: 10px 20px; background: #16a34a; color: white; text-decoration: none; border-radius: 5px;">Ativar conta</a></p>
            <p style="color: #999; font-size: 12px;">Se você não criou esta conta, ignore este email.</p>
        </body>
        </html>
        """
        text = f"""
{tenant_name}

Bem-vindo! Sua conta foi criada.
Acesse o link para ativar: {activation_link}

Se você não criou esta conta, ignore este email.
        """
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    async def send_welcome(
        self,
        *,
        to: str,
        full_name: str,
        frontend_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Welcome a public B2C account without ever including a password."""
        safe_name = escape(full_name)
        safe_tenant = escape(tenant_name)
        catalog_url = f"{frontend_url.rstrip('/')}/cursos"
        safe_catalog_url = escape(catalog_url, quote=True)
        subject = f"Bem-vindo à {tenant_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Sua conta foi criada com sucesso.</p>
            <p>Você já pode acessar a plataforma e escolher seus treinamentos.</p>
            <p><a href="{safe_catalog_url}" style="display: inline-block; padding: 10px 20px; background: #4f46e5; color: white; text-decoration: none; border-radius: 5px;">Ver cursos</a></p>
            <p style="color: #999; font-size: 12px;">Por segurança, sua senha nunca é enviada por e-mail.</p>
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            "Sua conta foi criada com sucesso. Você já pode acessar a plataforma "
            f"e escolher seus treinamentos: {catalog_url}\n\n"
            "Por segurança, sua senha nunca é enviada por e-mail."
        )
        return await self.send_email(
            to=to,
            subject=subject,
            html_body=html,
            text_body=text,
            from_name=tenant_name,
        )

    async def send_course_access(
        self,
        *,
        to: str,
        full_name: str,
        course_name: str,
        course_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Notify that payment was confirmed and course access is available."""
        safe_name = escape(full_name)
        safe_course = escape(course_name)
        safe_tenant = escape(tenant_name)
        safe_course_url = escape(course_url, quote=True)
        subject = f"Curso liberado — {course_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Seu pagamento foi confirmado e o acesso ao curso <strong>{safe_course}</strong> está liberado.</p>
            <p><a href="{safe_course_url}" style="display: inline-block; padding: 10px 20px; background: #16a34a; color: white; text-decoration: none; border-radius: 5px;">Acessar meu curso</a></p>
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            f"Seu pagamento foi confirmado e o curso {course_name} está liberado.\n"
            f"Acesse: {course_url}"
        )
        return await self.send_email(
            to=to,
            subject=subject,
            html_body=html,
            text_body=text,
            from_name=tenant_name,
        )

    async def send_payment_approved(
        self,
        *,
        to: str,
        full_name: str,
        course_name: str,
        amount: str,
        payment_method: str,
        course_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Notify that a payment has been approved."""
        safe_name = escape(full_name)
        safe_course = escape(course_name)
        safe_tenant = escape(tenant_name)
        safe_course_url = escape(course_url, quote=True)
        safe_amount = escape(str(amount))
        safe_method = escape(payment_method)
        subject = f"Pagamento confirmado — {course_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Seu pagamento para o curso <strong>{safe_course}</strong> foi confirmado.</p>
            <p style="color: #6B7280; font-size: 14px;">Valor: {safe_amount} · Método: {safe_method}</p>
            <p><a href="{safe_course_url}" style="display: inline-block; padding: 10px 20px; background: #16a34a; color: white; text-decoration: none; border-radius: 5px;">Acessar curso</a></p>
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            f"Seu pagamento para o curso {course_name} foi confirmado.\n"
            f"Valor: {amount} · Método: {payment_method}\n"
            f"Acesse: {course_url}"
        )
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    async def send_course_completed(
        self,
        *,
        to: str,
        full_name: str,
        course_name: str,
        certificate_url: str | None = None,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Notify that a course has been completed."""
        safe_name = escape(full_name)
        safe_course = escape(course_name)
        safe_tenant = escape(tenant_name)
        safe_cert_url = escape(certificate_url, quote=True) if certificate_url else None
        subject = f"Curso concluído — {course_name}"
        cert_html = ""
        cert_text = ""
        if certificate_url:
            cert_html = f'<p><a href="{safe_cert_url}" style="display: inline-block; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Ver certificado</a></p>'
            cert_text = f"\nCertificado: {certificate_url}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Parabéns! Você concluiu o curso <strong>{safe_course}</strong>.</p>
            {cert_html}
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            f"Parabéns! Você concluiu o curso {course_name}."
            f"{cert_text}"
        )
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    async def send_certificate_issued(
        self,
        *,
        to: str,
        full_name: str,
        course_name: str,
        certificate_number: str,
        validation_url: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Notify that a certificate has been issued."""
        safe_name = escape(full_name)
        safe_course = escape(course_name)
        safe_tenant = escape(tenant_name)
        safe_cert_num = escape(certificate_number)
        safe_validation_url = escape(validation_url, quote=True)
        subject = f"Certificado emitido — {course_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Seu certificado do curso <strong>{safe_course}</strong> foi emitido.</p>
            <p style="color: #6B7280; font-size: 14px;">Certificado nº {safe_cert_num}</p>
            <p><a href="{safe_validation_url}" style="display: inline-block; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Validar certificado</a></p>
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            f"Seu certificado do curso {course_name} foi emitido.\n"
            f"Certificado nº {certificate_number}\n"
            f"Validar: {validation_url}"
        )
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    async def send_certificate_expiration_warning(
        self,
        *,
        to: str,
        full_name: str,
        course_name: str,
        certificate_number: str,
        expires_at: str,
        tenant_name: str = "Plataforma",
    ) -> bool:
        """Warn that a certificate/training is nearing expiration."""
        safe_name = escape(full_name)
        safe_course = escape(course_name)
        safe_tenant = escape(tenant_name)
        safe_cert_num = escape(certificate_number)
        safe_expires = escape(expires_at)
        subject = f"Certificado próximo do vencimento — {course_name}"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{safe_tenant}</h2>
            <p>Olá, {safe_name}.</p>
            <p>Seu certificado do curso <strong>{safe_course}</strong> (nº {safe_cert_num}) vence em <strong>{safe_expires}</strong>.</p>
            <p>Para manter sua certificação atualizada, verifique os requisitos de reciclagem.</p>
        </body>
        </html>
        """
        text = (
            f"{tenant_name}\n\nOlá, {full_name}.\n\n"
            f"Seu certificado do curso {course_name} (nº {certificate_number}) "
            f"vence em {expires_at}.\n"
            f"Verifique os requisitos de reciclagem."
        )
        return await self.send_email(
            to=to, subject=subject, html_body=html, text_body=text, from_name=tenant_name
        )

    @property
    def sent_emails(self) -> list[dict[str, Any]]:
        """List of sent emails (for test inspection in mock mode)."""
        return self._sent


# Singleton instance (mock by default)
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get or create the singleton EmailService instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


def reset_email_service() -> None:
    """Reset the singleton (for tests)."""
    global _email_service
    _email_service = None
