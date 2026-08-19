import time

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from app.api.routes import (
    auth,
    certificates,
    classes,
    companies,
    courses,
    dashboard,
    enrollments,
    lessons,
    partner_leads,
    payments,
    plans,
    reports,
    students,
    super_admin,
    tenant_secrets,
    tenant_subscriptions,
    tenants,
)
from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.database import AsyncSession, AsyncSessionLocal, get_db
from app.core.logging_config import RequestLoggingMiddleware, setup_logging
from app.core.proxy import get_client_ip
from app.core.rate_limit import get_rate_limiter
from app.core.secrets import validate_production_config, validate_secrets
from app.core.tenant import TenantResolver

# Fail-closed: refuse to start in production with unsafe config.
validate_production_config()

# Structured logging
setup_logging()

app = FastAPI(
    title="Plataforma de Cursos",
    description="API para gestão de cursos e certificações",
    version="1.0.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)
app.add_middleware(GZipMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)


# Paths exempt from subscription enforcement (SUPER_ADMIN management,
# tenant branding read, partner leads, auth, health, public plans).
_ENFORCEMENT_EXEMPT_EXACT = frozenset({
    "/", "/health", "/health/live", "/health/ready",
    "/docs", "/redoc", "/openapi.json",
})
_ENFORCEMENT_EXEMPT_PREFIXES = (
    "/api/v1/super-admin",
    "/api/v1/partner-leads",
    "/api/v1/plans/public",
    "/api/v1/tenants/branding",
    "/api/v1/auth",
    "/health",
)


def _is_enforcement_exempt(request: Request) -> bool:
    path = request.url.path
    if path in _ENFORCEMENT_EXEMPT_EXACT:
        return True
    return any(path.startswith(p) for p in _ENFORCEMENT_EXEMPT_PREFIXES)


async def _get_tenant_subscription_status(tenant_id) -> str | None:
    """Returns the most recent subscription status for a tenant, or None."""
    from sqlalchemy import select as _select

    from app.models.tenant_subscription import TenantSubscription

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(
            text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        )
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        stmt = (
            _select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.updated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()
        return sub.status if sub else None


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting por IP usando o backend configurado (Memory ou Redis).

    Usa get_rate_limiter() para obter o singleton do backend, respeitando
    RATE_LIMIT_REDIS_URL. Evita criar nova conexão Redis por request.
    """
    if not settings.RATE_LIMIT_ENABLED or request.url.path in (
        "/health",
        "/health/live",
        "/health/ready",
        "/",
    ):
        return await call_next(request)

    client_host = get_client_ip(request)
    backend = get_rate_limiter()
    if not backend.is_allowed(
        client_host,
        settings.RATE_LIMIT_REQUESTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
        )
    return await call_next(request)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Resolve o tenant por host/custom domain e define o contexto da sessão."""
    # Framework-level paths that are never tenant-scoped: health probes, root,
    # and OpenAPI/Swagger docs (which may be disabled via DOCS_ENABLED). These
    # must bypass tenant resolution so they do not require DB connectivity.
    if request.url.path in (
        "/health",
        "/health/live",
        "/health/ready",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    ):
        return await call_next(request)

    resolver = TenantResolver()
    token = current_tenant_id.set(None)
    async with AsyncSessionLocal() as db:
        try:
            tenant = await resolver.resolve(request, db)
            token = current_tenant_id.set(tenant.id)
            request.state.tenant_id = tenant.id
            # Also store in raw ASGI scope for reliable propagation through
            # BaseHTTPMiddleware (request.state may not propagate in Starlette 0.27)
            request.scope["resolved_tenant_id"] = str(tenant.id)
        except HTTPException as exc:
            request.state.tenant_id = None
            if not (
                request.url.path.startswith("/api/v1/tenants")
                or request.url.path.startswith("/api/v1/partner-leads")
                or request.url.path.startswith("/api/v1/super-admin")
                or request.url.path.startswith("/api/v1/plans/public")
            ):
                current_tenant_id.reset(token)
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                )

    try:
        # Subscription enforcement: block tenant business operations when
        # SUSPENDED or CANCELLED. SUPER_ADMIN paths and public/system paths
        # are exempt so the WR operator can still manage the tenant.
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id and not _is_enforcement_exempt(request):
            sub_status = await _get_tenant_subscription_status(tenant_id)
            if sub_status in ("SUSPENDED", "CANCELLED"):
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": "Plataforma temporariamente indisponível.",
                        "subscription_status": sub_status,
                    },
                )
        return await call_next(request)
    finally:
        current_tenant_id.reset(token)

app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(
    partner_leads.router, prefix="/api/v1/partner-leads", tags=["partner-leads"]
)
app.include_router(
    dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"]
)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(classes.router, prefix="/api/v1/classes", tags=["classes"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(enrollments.router, prefix="/api/v1/enrollments", tags=["enrollments"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(
    tenant_subscriptions.router,
    prefix="/api/v1/subscriptions",
    tags=["subscriptions"],
)
app.include_router(
    super_admin.router,
    prefix="/api/v1/super-admin",
    tags=["super-admin"],
)
app.include_router(
    tenant_secrets.router,
    prefix="/api/v1/secrets",
    tags=["secrets"],
)
app.include_router(certificates.router, prefix="/api/v1/certificates", tags=["certificates"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["companies"])
app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["lessons"])

@app.get("/")
async def root():
    return {"message": "Plataforma de Cursos API", "version": "1.0.0"}

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    await db.execute(text("SELECT 1"))
    duration = round((time.perf_counter() - start) * 1000, 2)
    return {"status": "ok", "db_latency_ms": duration}


@app.get("/health/live")
async def health_live():
    """Liveness probe — process is alive. No dependency checks."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe — can serve requests. Checks DB connectivity.

    Uses a dedicated DB session created directly inside the route's try block
    instead of the ``get_db`` dependency. ``get_db`` executes
    ``SET LOCAL app.current_tenant = ...`` before yielding the session, so if
    PostgreSQL is unavailable the dependency raises before this handler runs —
    producing an uncontrolled 500 instead of the intended 503.

    This probe intentionally avoids tenant RLS context: it is a process-level
    connectivity check, not a tenant-scoped request. SQLAlchemy connectivity
    failures (OperationalError/InterfaceError) and low-level socket errors
    (OSError) are mapped to 503 ``not_ready``.
    """
    start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        duration = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "db_latency_ms": duration}
    except (OperationalError, InterfaceError, OSError) as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": type(exc).__name__},
        )


@app.get("/api/v1/health/secrets")
async def health_secrets():
    issues = validate_secrets()
    if issues:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "warning", "issues": issues},
        )
    return {"status": "ok"}
