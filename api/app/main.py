import time

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError

from app.api.routes import (
    asaas_integration,
    assessments,
    auth,
    certificate_documents,
    certificate_signing,
    certificates,
    classes,
    companies,
    compliance,
    compliance_operations,
    corporate,
    corporate_invites,
    course_content,
    course_materials,
    courses,
    dashboard,
    enrollments,
    financial_admin,
    governance,
    lessons,
    partner_leads,
    payments,
    plans,
    privacy,
    reconciliation,
    regulatory_assessment_guards,
    regulatory_legacy_guards,
    reports,
    storage,
    students,
    super_admin,
    tenant_secrets,
    tenant_subscriptions,
    tenants,
    training_evidence,
    trusted_certificate_guards,
    tutor,
)
from app.core.audit import AdminAuditMiddleware
from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.database import AsyncSession, AsyncSessionLocal, get_db
from app.core.logging_config import RequestLoggingMiddleware, setup_logging
from app.core.proxy import get_client_ip
from app.core.rate_limit import get_rate_limiter
from app.core.secrets import validate_production_config, validate_secrets
from app.core.tenant import TenantResolver

validate_production_config()
setup_logging()

app = FastAPI(
    title="Plataforma de Cursos",
    description="API para gestão de cursos e certificações",
    version="1.0.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AdminAuditMiddleware)

_ENFORCEMENT_EXEMPT_EXACT = frozenset({
    "/", "/health", "/health/live", "/health/ready", "/docs", "/redoc", "/openapi.json",
})
_ENFORCEMENT_EXEMPT_PREFIXES = (
    "/api/v1/super-admin",
    "/api/v1/partner-leads",
    "/api/v1/plans/public",
    "/api/v1/tenants/branding",
    "/api/v1/auth",
    "/api/v1/integrations/certificate-signing/webhook",
    "/health",
)


def _is_enforcement_exempt(request: Request) -> bool:
    path = request.url.path
    return path in _ENFORCEMENT_EXEMPT_EXACT or any(
        path.startswith(prefix) for prefix in _ENFORCEMENT_EXEMPT_PREFIXES
    )


async def _get_tenant_subscription_status(tenant_id) -> str | None:
    from sqlalchemy import select as _select

    from app.models.tenant_subscription import TenantSubscription

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        result = await db.execute(
            _select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.updated_at.desc())
            .limit(1)
        )
        subscription = result.scalar_one_or_none()
        return subscription.status if subscription else None


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, exc: IntegrityError):
    if "uq_company_tenant_cnpj" in str(exc.orig):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Company with this CNPJ already exists"},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database integrity error"},
    )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED or request.url.path in (
        "/health", "/health/live", "/health/ready", "/",
    ):
        return await call_next(request)
    backend = get_rate_limiter()
    if not backend.is_allowed(
        get_client_ip(request),
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
    if request.url.path in (
        "/health", "/health/live", "/health/ready", "/", "/docs", "/redoc", "/openapi.json",
    ):
        return await call_next(request)
    resolver = TenantResolver()
    token = current_tenant_id.set(None)
    async with AsyncSessionLocal() as db:
        try:
            tenant = await resolver.resolve(request, db)
            token = current_tenant_id.set(tenant.id)
            request.state.tenant_id = tenant.id
            request.scope["resolved_tenant_id"] = str(tenant.id)
        except HTTPException as exc:
            request.state.tenant_id = None
            if not (
                request.url.path.startswith("/api/v1/tenants")
                or request.url.path.startswith("/api/v1/partner-leads")
                or request.url.path.startswith("/api/v1/super-admin")
                or request.url.path.startswith("/api/v1/plans/public")
                or request.url.path.startswith("/api/v1/integrations/certificate-signing/webhook")
            ):
                current_tenant_id.reset(token)
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    try:
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
app.include_router(partner_leads.router, prefix="/api/v1/partner-leads", tags=["partner-leads"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(classes.router, prefix="/api/v1/classes", tags=["classes"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(enrollments.router, prefix="/api/v1/enrollments", tags=["enrollments"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(financial_admin.router, prefix="/api/v1/financial", tags=["financial-admin"])
app.include_router(reconciliation.router, prefix="/api/v1/financial/reconciliation", tags=["financial-reconciliation"])
app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])
app.include_router(privacy.router, prefix="/api/v1/privacy", tags=["privacy"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["nr-compliance"])
app.include_router(
    compliance_operations.router,
    prefix="/api/v1/compliance/operations",
    tags=["compliance-operations"],
)
app.include_router(training_evidence.router, prefix="/api/v1/training-evidence", tags=["training-evidence"])
# Compatibility guards are registered before the legacy routers so existing
# clients keep their URLs while regulated enrollments cannot bypass the new
# completion/document state machines. They are hidden from OpenAPI.
app.include_router(regulatory_assessment_guards.router, prefix="/api/v1")
app.include_router(regulatory_legacy_guards.router, prefix="/api/v1")
app.include_router(trusted_certificate_guards.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(tenant_subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"])
app.include_router(super_admin.router, prefix="/api/v1/super-admin", tags=["super-admin"])
app.include_router(tenant_secrets.router, prefix="/api/v1/secrets", tags=["secrets"])
app.include_router(certificate_documents.router, prefix="/api/v1/certificate-documents", tags=["certificate-documents"])
app.include_router(certificate_signing.router, prefix="/api/v1/certificate-signing", tags=["certificate-signing"])
app.include_router(certificates.router, prefix="/api/v1/certificates", tags=["certificates"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["companies"])
app.include_router(corporate.router, prefix="/api/v1/corporate", tags=["corporate"])
app.include_router(corporate_invites.router, prefix="/api/v1/corporate", tags=["corporate-invites"])
app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["lessons"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["assessments"])
app.include_router(storage.router, prefix="/api/v1/storage", tags=["storage"])
app.include_router(course_content.router, prefix="/api/v1", tags=["course-content"])
app.include_router(course_materials.router, prefix="/api/v1", tags=["course-materials"])
app.include_router(
    asaas_integration.router,
    prefix="/api/v1/integrations/asaas",
    tags=["asaas-integration"],
)
app.include_router(
    certificate_signing.webhook_router,
    prefix="/api/v1/integrations/certificate-signing",
    tags=["certificate-signing-webhook"],
)
app.include_router(tutor.router, prefix="/api/v1/tutor", tags=["tutor"])


@app.get("/")
async def root():
    return {"message": "Plataforma de Cursos API", "version": "1.0.0"}


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db_latency_ms": round((time.perf_counter() - start) * 1000, 2)}


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "db_latency_ms": round((time.perf_counter() - start) * 1000, 2)}
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
