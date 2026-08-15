"""Validações básicas de hardening de configurações sensíveis."""

from app.core.config import settings


def validate_secret_key() -> list[str]:
    """Verifica se a SECRET_KEY é forte o suficiente."""
    issues = []
    if len(settings.SECRET_KEY) < 32:
        issues.append("SECRET_KEY must be at least 32 characters")
    if settings.SECRET_KEY in (
        "your-secret-key-change-in-production",
        "secret",
        "changeme",
    ):
        issues.append("SECRET_KEY is using a default/placeholder value")
    return issues


def validate_allowed_hosts() -> list[str]:
    """Verifica se ALLOWED_HOSTS está restringido em produção."""
    issues = []
    if "*" in settings.ALLOWED_HOSTS:
        issues.append("ALLOWED_HOSTS should not allow wildcard '*' in production")
    return issues


def validate_secrets() -> list[str]:
    """Retorna lista de problemas de hardening encontrados."""
    return validate_secret_key() + validate_allowed_hosts()
