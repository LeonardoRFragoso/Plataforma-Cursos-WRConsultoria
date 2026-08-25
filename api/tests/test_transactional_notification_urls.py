from app.core.config import settings
from app.models.tenant import CustomDomainStatus, Tenant
from app.services.transactional_notifications import (
    _safe_http_base_url,
    _tenant_frontend_url,
)


def _tenant(**overrides):
    data = {
        "name": "Academia Teste",
        "slug": "academia-teste",
        "contact_name": "Contato",
        "contact_email": "contato@example.com",
        "custom_domain_status": CustomDomainStatus.NONE,
        "settings": {},
    }
    data.update(overrides)
    return Tenant(**data)


def test_safe_http_base_url_accepts_only_absolute_http_urls():
    assert _safe_http_base_url("https://academy.example.com/") == "https://academy.example.com"
    assert _safe_http_base_url("http://localhost:5173") == "http://localhost:5173"

    assert _safe_http_base_url("javascript:alert(1)") is None
    assert _safe_http_base_url("ftp://academy.example.com") is None
    assert _safe_http_base_url("https://user:pass@academy.example.com") is None
    assert _safe_http_base_url("https://academy.example.com:not-a-port") is None
    assert _safe_http_base_url("https://academy.example.com\nBcc:evil@example.com") is None


def test_unsafe_tenant_frontend_url_falls_back_to_application_url(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://wr.example.com")
    tenant = _tenant(settings={"frontend_url": "javascript:alert(1)"})

    assert _tenant_frontend_url(tenant) == "https://wr.example.com"


def test_verified_custom_domain_is_preferred_over_settings(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://wr.example.com")
    tenant = _tenant(
        custom_domain="academy.customer.com",
        custom_domain_status=CustomDomainStatus.VERIFIED,
        settings={"frontend_url": "https://fallback.customer.com"},
    )

    assert _tenant_frontend_url(tenant) == "https://academy.customer.com"


def test_unverified_custom_domain_is_not_used(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://wr.example.com")
    tenant = _tenant(
        custom_domain="pending.customer.com",
        custom_domain_status=CustomDomainStatus.PENDING,
        settings={"frontend_url": "https://academy.customer.com"},
    )

    assert _tenant_frontend_url(tenant) == "https://academy.customer.com"
