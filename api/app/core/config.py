
import uuid as _uuid

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SSO_SECRET = "change-me-sso-secret"
_MIN_SECRET_LENGTH = 32


def _normalize_database_url(url: str) -> str:
    """Normalize the DATABASE_URL scheme for SQLAlchemy async (asyncpg).

    Railway and other platforms may expose ``postgres://`` or
    ``postgresql://`` URLs. SQLAlchemy async requires
    ``postgresql+asyncpg://``. Only the scheme is replaced; host, port,
    credentials, database name, and query parameters are preserved.

    Non-PostgreSQL schemes (e.g. sqlite) are returned unchanged.
    """
    if not url:
        return url
    # Only normalize known PostgreSQL schemes. Leave everything else
    # (sqlite, mysql, etc.) untouched so we don't silently convert
    # unrelated databases.
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            return url  # already async-compatible
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return _normalize_database_url(v)
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Multi-tenant frontend context trust.
    # When the API is served on a different host than the frontend (e.g.
    # Vercel + Railway), the backend cannot derive the tenant from its own
    # Host header. The frontend sends X-Tenant-Slug, but only Origins listed
    # here are allowed to set it in staging/production. Empty list = trust
    # nobody via this header (fall back to Host/custom_domain resolution).
    TRUSTED_FRONTEND_ORIGINS: list[str] = []

    # Master host used by TenantResolver to map "the API's own host" to the
    # WR tenant (e.g. the Railway API hostname). Defaults to localhost.
    MASTER_HOST: str = "localhost"

    # SSO — Central WR as Identity Provider
    CENTRAL_WR_FRONTEND_URL: str = "http://localhost:5173"
    CENTRAL_WR_BACKEND_URL: str = "http://localhost:8000"
    CENTRAL_WR_SSO_CLIENT_ID: str = "lms-wr-cursos"
    CENTRAL_WR_SSO_CLIENT_SECRET: str = "change-me-sso-secret"
    # The tenant_id (UUID) of the Central WR tenant that is trusted to
    # send ADMIN users via SSO. This is the Central WR tenant UUID — it
    # is NOT the same as WR_TENANT_ID (the LMS's internal tenant).
    # When set, the LMS validates that claims["tenant_id"] matches this
    # value before provisioning or linking any user.
    CENTRAL_WR_TRUSTED_TENANT_ID: str = ""

    # Demo/staging seed gate. The demo seed script refuses to run unless
    # this is true AND ENVIRONMENT != production.
    DEMO_SEED_MODE: bool = False
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Quando definida, o rate limiter usa Redis (compartilhado entre workers).
    RATE_LIMIT_REDIS_URL: str = ""
    B2B_RATE_LIMIT_REQUESTS: int = 120
    B2B_RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Pre-auth IP-based limit for B2B endpoints — prevents rotating fake
    # client IDs to bypass per-client quota. Applied before authentication.
    B2B_PREAUTH_RATE_LIMIT_REQUESTS: int = 200
    B2B_PREAUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    # Global default payment provider. Per-tenant settings["payment_provider"]
    # overrides this, BUT only if the selected provider is in
    # PAYMENT_PROVIDERS_ENABLED. If a tenant selects a provider that is not
    # enabled, resolve_provider() fails closed (raises).
    # Accepted values: "ASAAS", "MERCADO_PAGO".
    PAYMENT_PROVIDER: str = "MERCADO_PAGO"
    # Comma-separated list of providers that are allowed to be used at runtime.
    # If empty, defaults to [PAYMENT_PROVIDER] for backwards compatibility.
    # In production, ALL providers in this list must pass their respective
    # safety validations (mock mode off, webhook URL set, etc.).
    # Example: "ASAAS,MERCADO_PAGO" for multi-provider.
    PAYMENT_PROVIDERS_ENABLED: str = ""
    MERCADO_PAGO_ACCESS_TOKEN: str = ""
    MERCADO_PAGO_PUBLIC_KEY: str = ""
    MERCADO_PAGO_MOCK_MODE: bool = False

    # Provider-less PENDENTE attempts can be safely expired locally after this
    # interval. Attempts that already created an external charge are never
    # expired by this timer; provider webhooks remain authoritative for them.
    PAYMENT_PENDING_ATTEMPT_TTL_MINUTES: int = 30

    # Asaas gateway — per-tenant API keys live in TenantSecret.
    # ASAAS_MOCK_MODE makes AsaasProvider return deterministic fakes
    # without touching the network (tests/staging only).
    ASAAS_MOCK_MODE: bool = False
    # Base URL for the backend's public API. Used to build the Asaas
    # webhook callback URL: {API_BASE_URL}/api/v1/integrations/asaas/webhook/{slug}
    # In production this MUST be the publicly reachable URL.
    ASAAS_WEBHOOK_BASE_URL: str = ""

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    # Mock mode: emails are not sent, just logged and stored for inspection.
    # Defaults to True for safety — production must explicitly set to False.
    EMAIL_MOCK_MODE: bool = True
    # Explicit email enable/disable. When False, email-related features
    # (password reset, activation) are silently skipped. When True +
    # EMAIL_MOCK_MODE=True, emails are logged but not sent (dev/test).
    # When True + EMAIL_MOCK_MODE=False, real SMTP is used (production).
    EMAIL_ENABLED: bool = True
    
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:4173",
    ]
    
    ALLOWED_HOSTS: list[str] = ["*"]
    
    # Storage S3-compatível (Cloudflare R2 / Backblaze B2 / MinIO / AWS S3)
    # STORAGE_BACKEND: "s3" (default, production) or "local" (development)
    STORAGE_BACKEND: str = "s3"
    STORAGE_ENDPOINT: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_BUCKET: str = "wr-videos"
    STORAGE_REGION: str = "auto"
    STORAGE_WATCH_URL_EXPIRATION: int = 7200  # segundos

    # Local storage directory (only used when STORAGE_BACKEND=local)
    STORAGE_LOCAL_DIR: str = ".local_storage"

    # Backend's own base URL — used to build local upload/serve URLs.
    # In development this is the API server URL. In production it is the
    # public API URL (may differ from FRONTEND_URL which is the web app).
    API_BASE_URL: str = "http://localhost:8000"

    # Chave de criptografia para secrets de tenant (32 bytes base64).
    # Em produção deve ser definida via env. Se vazia, fallback para uma
    # chave derivada da SECRET_KEY (apenas desenvolvimento).
    TENANT_SECRET_ENCRYPTION_KEY: str = ""

    # Comma-separated list of trusted proxy IPs/CIDRs for X-Forwarded-For.
    # Only these proxies' X-Forwarded-For headers are trusted for client IP.
    # Empty = do not trust any forwarded IP (use direct connection IP).
    TRUSTED_PROXY_CIDRS: str = ""

    # Expose Swagger/OpenAPI docs. Set to false in production.
    DOCS_ENABLED: bool = True

    @property
    def payment_providers_enabled_list(self) -> list[str]:
        """Return the list of explicitly enabled payment providers (uppercased).

        Returns [] if PAYMENT_PROVIDERS_ENABLED is empty. In non-production
        environments, resolve_provider() treats an empty list as "all
        recognized providers allowed" (legacy/staging backward compat).
        In production, an empty list causes startup to fail (explicit config
        required).
        """
        raw = self.PAYMENT_PROVIDERS_ENABLED.strip()
        if not raw:
            return []
        return [p.strip().upper() for p in raw.split(",") if p.strip()]

    @model_validator(mode="after")
    def _validate_sso_production_hardening(self) -> "Settings":
        """Block startup in production if SSO configuration is insecure.

        In production:
        - CENTRAL_WR_SSO_CLIENT_SECRET must not be the default, must not
          be empty, and must be at least 32 characters.
        - CENTRAL_WR_TRUSTED_TENANT_ID must be set, non-empty, and a valid
          UUID. This prevents the defense-in-depth tenant check from being
          silently disabled in production.
        - CENTRAL_WR_FRONTEND_URL and CENTRAL_WR_BACKEND_URL must use
          HTTPS (browser redirects must never go to http:// in production).
        """
        if self.ENVIRONMENT.lower() != "production":
            return self

        secret = self.CENTRAL_WR_SSO_CLIENT_SECRET
        if not secret:
            raise ValueError(
                "CENTRAL_WR_SSO_CLIENT_SECRET must be set in production "
                "(empty value not allowed)."
            )
        if secret == _INSECURE_DEFAULT_SSO_SECRET:
            raise ValueError(
                "CENTRAL_WR_SSO_CLIENT_SECRET must be set to a strong secret in "
                "production (the default 'change-me-sso-secret' is not allowed)."
            )
        if len(secret) < _MIN_SECRET_LENGTH:
            raise ValueError(
                f"CENTRAL_WR_SSO_CLIENT_SECRET must be at least {_MIN_SECRET_LENGTH} "
                f"characters in production (got {len(secret)}). "
                f"Use a randomly generated secret."
            )

        # CENTRAL_WR_TRUSTED_TENANT_ID must be a valid UUID in production.
        # An empty value would silently disable the defense-in-depth tenant
        # check in _validate_claims(), allowing any Central WR tenant to SSO.
        trusted = self.CENTRAL_WR_TRUSTED_TENANT_ID
        if not trusted:
            raise ValueError(
                "CENTRAL_WR_TRUSTED_TENANT_ID must be set in production "
                "(empty value not allowed). Set it to the UUID of the WR "
                "tenant in Central WR — NOT the LMS's WR_TENANT_ID."
            )
        try:
            _uuid.UUID(trusted)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                f"CENTRAL_WR_TRUSTED_TENANT_ID must be a valid UUID in "
                f"production (got '{trusted}')."
            ) from exc

        # HTTPS validation for browser-facing URLs
        for field_name, url in [
            ("CENTRAL_WR_FRONTEND_URL", self.CENTRAL_WR_FRONTEND_URL),
            ("CENTRAL_WR_BACKEND_URL", self.CENTRAL_WR_BACKEND_URL),
        ]:
            if url and not url.startswith("https://"):
                raise ValueError(
                    f"{field_name} must use HTTPS in production (got '{url}'). "
                    f"Browser redirects must never go to http://."
                )

        # Payment provider explicit configuration required in production.
        # PAYMENT_PROVIDERS_ENABLED must not be empty, PAYMENT_PROVIDER must
        # be in the enabled list, and all enabled providers must be recognized.
        enabled = self.payment_providers_enabled_list
        if not enabled:
            raise ValueError(
                "PAYMENT_PROVIDERS_ENABLED must not be empty in production. "
                "Set it explicitly (e.g., 'ASAAS' or 'ASAAS,MERCADO_PAGO')."
            )
        recognized = {"ASAAS", "MERCADO_PAGO"}
        unknown = set(enabled) - recognized
        if unknown:
            raise ValueError(
                f"PAYMENT_PROVIDERS_ENABLED contains unrecognized providers: "
                f"{', '.join(sorted(unknown))}. Recognized: {', '.join(sorted(recognized))}."
            )
        default = self.PAYMENT_PROVIDER.upper()
        if default not in enabled:
            raise ValueError(
                f"PAYMENT_PROVIDER '{default}' must be in "
                f"PAYMENT_PROVIDERS_ENABLED ({', '.join(enabled)}) in production."
            )

        return self


settings = Settings()
