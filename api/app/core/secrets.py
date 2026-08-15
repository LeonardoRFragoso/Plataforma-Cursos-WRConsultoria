"""Validações de hardening de configurações sensíveis.

Em produção (ENVIRONMENT=production), a aplicação NÃO deve iniciar
com configurações inseguras. As validações são executadas no startup
via `validate_production_config()` que levanta `RuntimeError` se
qualquer validação P0 falhar.

Em desenvolvimento/teste, as validações são expostas via
`/api/v1/health/secrets` para diagnóstico, mas não bloqueiam o startup.
"""

import os

from app.core.config import settings

PLACEHOLDER_SECRET_KEYS = (
    "your-secret-key-change-in-production",
    "your-super-secret-key-change-in-production",
    "secret",
    "changeme",
    "test-secret-key-at-least-32-characters-long",
)


def validate_secret_key() -> list[str]:
    """Verifica se a SECRET_KEY é forte o suficiente."""
    issues = []
    if len(settings.SECRET_KEY) < 32:
        issues.append("SECRET_KEY must be at least 32 characters")
    if settings.SECRET_KEY in PLACEHOLDER_SECRET_KEYS:
        issues.append("SECRET_KEY is using a default/placeholder value")
    return issues


def validate_allowed_hosts() -> list[str]:
    """Verifica se ALLOWED_HOSTS está restringido em produção."""
    issues = []
    if "*" in settings.ALLOWED_HOSTS:
        issues.append("ALLOWED_HOSTS should not allow wildcard '*' in production")
    return issues


def validate_tenant_secret_encryption_key() -> list[str]:
    """Verifica se TENANT_SECRET_ENCRYPTION_KEY está definida em produção."""
    issues = []
    if not settings.TENANT_SECRET_ENCRYPTION_KEY:
        issues.append(
            "TENANT_SECRET_ENCRYPTION_KEY is empty — must be set in production"
        )
    return issues


def validate_mercado_pago_mock_mode() -> list[str]:
    """Verifica se MERCADO_PAGO_MOCK_MODE não está ativo em produção."""
    issues = []
    if settings.MERCADO_PAGO_MOCK_MODE:
        issues.append("MERCADO_PAGO_MOCK_MODE must be false in production")
    return issues


def validate_e2e_test_mode() -> list[str]:
    """Verifica se E2E_TEST_MODE não está ativo em produção."""
    issues = []
    if os.environ.get("E2E_TEST_MODE", "").lower() in ("true", "1", "yes"):
        issues.append("E2E_TEST_MODE must not be enabled in production")
    return issues


def validate_cors_origins() -> list[str]:
    """Verifica se CORS_ORIGINS não contém wildcards ou localhost em produção."""
    issues = []
    for origin in settings.CORS_ORIGINS:
        if "*" in origin:
            issues.append(f"CORS_ORIGINS contains wildcard: {origin}")
        if "localhost" in origin or "127.0.0.1" in origin:
            issues.append(f"CORS_ORIGINS contains localhost: {origin}")
    return issues


def validate_rate_limit_enabled() -> list[str]:
    """Verifica se rate limiting está habilitado em produção."""
    issues = []
    if not settings.RATE_LIMIT_ENABLED:
        issues.append("RATE_LIMIT_ENABLED is false — should be true in production")
    return issues


def validate_secrets() -> list[str]:
    """Retorna lista de problemas de hardening encontrados (não bloqueia)."""
    return (
        validate_secret_key()
        + validate_allowed_hosts()
        + validate_tenant_secret_encryption_key()
        + validate_mercado_pago_mock_mode()
        + validate_e2e_test_mode()
        + validate_cors_origins()
        + validate_rate_limit_enabled()
    )


def validate_production_config() -> None:
    """Valida configuração no startup. Levanta RuntimeError se insegura.

    Só valida quando ENVIRONMENT=production. Em development/test,
    não faz nada (permite defaults inseguros para conveniência local).
    """
    if settings.ENVIRONMENT != "production":
        return

    issues = validate_secrets()
    if issues:
        raise RuntimeError(
            "Production configuration is unsafe. Application will not start.\n"
            + "\n".join(f"  - {issue}" for issue in issues)
        )
