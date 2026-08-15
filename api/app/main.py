import time

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

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
    tenant_subscriptions,
    tenants,
)
from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.database import AsyncSession, AsyncSessionLocal, get_db
from app.core.rate_limit import limiter
from app.core.secrets import validate_secrets
from app.core.tenant import TenantResolver

app = FastAPI(
    title="Plataforma de Cursos",
    description="API para gestão de cursos e certificações",
    version="1.0.0",
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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting básico por IP."""
    if not settings.RATE_LIMIT_ENABLED or request.url.path in ("/health", "/"):
        return await call_next(request)

    client_host = request.client.host if request.client else "unknown"
    if not limiter.is_allowed(client_host):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
        )
    return await call_next(request)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Resolve o tenant por host/custom domain e define o contexto da sessão."""
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    resolver = TenantResolver()
    token = current_tenant_id.set(None)
    async with AsyncSessionLocal() as db:
        try:
            tenant = await resolver.resolve(request, db)
            token = current_tenant_id.set(tenant.id)
            request.state.tenant_id = tenant.id
        except HTTPException:
            request.state.tenant_id = None
            if not (
                request.url.path.startswith("/api/v1/tenants")
                or request.url.path.startswith("/api/v1/partner-leads")
            ):
                current_tenant_id.reset(token)
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Tenant not found"},
                )

    try:
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


@app.get("/api/v1/health/secrets")
async def health_secrets():
    issues = validate_secrets()
    if issues:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "warning", "issues": issues},
        )
    return {"status": "ok"}
