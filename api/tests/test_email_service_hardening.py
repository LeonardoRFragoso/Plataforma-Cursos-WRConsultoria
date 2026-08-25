import asyncio

import pytest

from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_email_headers_strip_crlf_in_mock_mode():
    service = EmailService(mock=True)

    assert await service.send_email(
        to="student@example.com",
        subject="Curso liberado\r\nBcc: attacker@example.com",
        html_body="<p>ok</p>",
        from_name="Academia\nInjected",
    )

    sent = service.sent_emails[0]
    assert "\r" not in sent["subject"]
    assert "\n" not in sent["subject"]
    assert sent["subject"] == "Curso liberado Bcc: attacker@example.com"


@pytest.mark.asyncio
async def test_real_smtp_delivery_is_offloaded_from_event_loop(monkeypatch):
    service = EmailService(
        smtp_server="smtp.example.com",
        smtp_port=587,
        smtp_user="mailer@example.com",
        smtp_password="secret",
        mock=False,
    )
    delivered = {"value": False, "to_thread": False}

    def fake_delivery(to, message):
        delivered["value"] = True
        assert to == "student@example.com"
        assert "Subject: Teste" in message

    async def fake_to_thread(func, *args, **kwargs):
        delivered["to_thread"] = True
        return func(*args, **kwargs)

    monkeypatch.setattr(service, "_send_smtp_message", fake_delivery)
    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    assert await service.send_email(
        to="student@example.com",
        subject="Teste",
        html_body="<p>ok</p>",
    )
    assert delivered == {"value": True, "to_thread": True}


@pytest.mark.asyncio
async def test_welcome_and_course_links_are_html_escaped():
    service = EmailService(mock=True)

    await service.send_welcome(
        to="student@example.com",
        full_name="Aluno <Teste>",
        frontend_url='https://academy.example.com/?next="catalog"',
        tenant_name="Academia & Cursos",
    )
    await service.send_course_access(
        to="student@example.com",
        full_name="Aluno <Teste>",
        course_name="NR <10>",
        course_url='https://academy.example.com/course?id=1&from="email"',
        tenant_name="Academia & Cursos",
    )

    welcome_html = service.sent_emails[0]["html_body"]
    course_html = service.sent_emails[1]["html_body"]

    assert "Aluno &lt;Teste&gt;" in welcome_html
    assert "Academia &amp; Cursos" in welcome_html
    assert "&quot;catalog&quot;" in welcome_html
    assert "NR &lt;10&gt;" in course_html
    assert "&amp;from=&quot;email&quot;" in course_html
