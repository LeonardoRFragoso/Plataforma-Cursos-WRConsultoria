import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.normalization import normalize_email, validate_cpf
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.certificate import Certificate
from app.models.company import Company
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.schemas.student import StudentResponse
from app.services.email_service import EmailServiceError, get_email_service
from app.services.one_time_token_service import OneTimeTokenService

router = APIRouter()

# Environments where raw one-time tokens may be returned in responses.
# Only local development and automated test environments.
_LOCAL_TOKEN_RETURN_ENVS = frozenset({"development", "dev", "test", "testing"})


def _current_env() -> str:
    return getattr(settings, "ENVIRONMENT", "").lower()


def _can_return_token() -> bool:
    """Only local dev/test environments may return raw one-time tokens."""
    return _current_env() in _LOCAL_TOKEN_RETURN_ENVS


def _clean_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ."""
    return cnpj.replace('.', '').replace('-', '').replace('/', '').strip()


# ---------------------------------------------------------------------------
# Company CRUD (tenant-isolated)
# ---------------------------------------------------------------------------

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    raw_cnpj = _clean_cnpj(company_data.cnpj)

    stmt = select(Company).where(
        Company.tenant_id == tenant_id,
        Company.cnpj == raw_cnpj,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company with this CNPJ already exists",
        )

    company = Company(
        tenant_id=tenant_id,
        legal_name=company_data.legal_name,
        trade_name=company_data.trade_name,
        cnpj=raw_cnpj,
        rh_name=company_data.rh_name,
        rh_email=str(company_data.rh_email) if company_data.rh_email else None,
        rh_phone=company_data.rh_phone,
        billing_email=str(company_data.billing_email) if company_data.billing_email else None,
        contract_reference=company_data.contract_reference,
        status=company_data.status.upper(),
        notes=company_data.notes,
        address=company_data.address,
        city=company_data.city,
        state=company_data.state,
        zip_code=company_data.zip_code,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Company)
        .where(Company.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
        .order_by(Company.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    update_data = company_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "cnpj" and value:
            value = _clean_cnpj(value)
        if field in {"rh_email", "billing_email"} and value:
            value = str(value)
        if field == "status" and value:
            value = value.upper()
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    await db.delete(company)
    await db.commit()


# ---------------------------------------------------------------------------
# Company Detail Stats
# ---------------------------------------------------------------------------

class CompanyStatsResponse(BaseModel):
    total_employees: int
    enrolled_employees: int
    active_enrollments: int
    completed_enrollments: int
    certificates_issued: int


@router.get("/{company_id}/stats", response_model=CompanyStatsResponse)
async def get_company_stats(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()

    # Verify company belongs to tenant
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Total employees
    total_employees = (
        await db.execute(
            select(func.count(Student.id)).where(
                Student.company_id == company_id,
                Student.tenant_id == tenant_id,
            )
        )
    ).scalar_one()

    # Enrollments for company employees
    enrollment_stmt = (
        select(Enrollment)
        .join(Student, Enrollment.student_id == Student.id)
        .where(
            Student.company_id == company_id,
            Enrollment.tenant_id == tenant_id,
        )
    )
    enrollments = (await db.execute(enrollment_stmt)).scalars().all()

    enrolled_employees = len({e.student_id for e in enrollments})
    active_enrollments = len([
        e for e in enrollments
        if e.status in (EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA)
    ])
    completed_enrollments = len([
        e for e in enrollments if e.status == EnrollmentStatus.CONCLUIDA
    ])

    # Certificates issued to company employees
    certificates_issued = (
        await db.execute(
            select(func.count(Certificate.id))
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .join(Student, Enrollment.student_id == Student.id)
            .where(
                Student.company_id == company_id,
                Certificate.tenant_id == tenant_id,
            )
        )
    ).scalar_one()

    return CompanyStatsResponse(
        total_employees=total_employees,
        enrolled_employees=enrolled_employees,
        active_enrollments=active_enrollments,
        completed_enrollments=completed_enrollments,
        certificates_issued=certificates_issued,
    )


# ---------------------------------------------------------------------------
# Company Employees
# ---------------------------------------------------------------------------

@router.get("/{company_id}/employees", response_model=list[StudentResponse])
async def list_company_employees(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(Student)
        .where(
            Student.company_id == company_id,
            Student.tenant_id == tenant_id,
        )
        .options(selectinload(Student.user))
        .order_by(Student.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Add Employee (with activation token)
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    full_name: str
    cpf: str
    email: str
    phone: str | None = None


class EmployeeCreateResponse(BaseModel):
    student: StudentResponse
    activation_token: str | None = None  # ONLY populated in dev/test envs
    activation_email_sent: bool = False


@router.post("/{company_id}/employees", response_model=EmployeeCreateResponse, status_code=status.HTTP_201_CREATED)
async def add_employee(
    company_id: UUID,
    employee_data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Create a corporate employee (User + Student) linked to a company.

    The user is created without a password. An activation token is generated
    so the employee can set their own password via the activation flow.

    In production/staging, the raw activation token is NEVER returned in the
    HTTP response. The token is sent to the employee via email. In local
    dev/test environments, the raw token is returned for automated tests.
    """
    tenant_id = get_current_tenant_id()

    # Verify company belongs to tenant
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Strict CPF validation — rejects invalid formats and check digits.
    try:
        raw_cpf = validate_cpf(employee_data.cpf)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF inválido",
        )

    normalized_employee_email = normalize_email(employee_data.email)

    # Check duplicate CPF (tenant-scoped)
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.cpf == raw_cpf,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CPF already registered")

    # Check duplicate email (tenant-scoped, case-insensitive via normalization)
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.email == normalized_employee_email,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create user without password — activation required.
    # User is born INACTIVE: login is impossible until /auth/activate
    # sets the password hash and flips is_active to True atomically.
    user = User(
        tenant_id=tenant_id,
        email=normalized_employee_email,
        cpf=raw_cpf,
        full_name=employee_data.full_name,
        password_hash=None,
        role=UserRole.STUDENT,
        is_active=False,
    )
    db.add(user)
    await db.flush()

    student = Student(
        tenant_id=tenant_id,
        user_id=user.id,
        cpf=raw_cpf,
        phone=employee_data.phone,
        company_id=company_id,
        company=company.trade_name or company.legal_name,
    )
    db.add(student)
    await db.flush()

    # Generate activation token
    raw_token, _ = await OneTimeTokenService.create(
        db, str(user.id), "activation", ttl_hours=168,  # 7 days
    )

    await db.commit()
    await db.refresh(student)
    await db.refresh(student, ["user"])

    # In production/staging: send activation email, NEVER expose raw token.
    # In dev/test: return raw token for automated tests.
    activation_email_sent = False
    returned_token = None
    if _can_return_token():
        returned_token = raw_token
    else:
        try:
            email_service = get_email_service()
            await email_service.send_account_activation(
                to=user.email,
                activation_token=raw_token,
                frontend_url=settings.FRONTEND_URL,
                tenant_name="Plataforma",
            )
            activation_email_sent = True
        except EmailServiceError:
            pass  # Don't fail the operation if email fails

    return EmployeeCreateResponse(
        student=StudentResponse.model_validate(student),
        activation_token=returned_token,
        activation_email_sent=activation_email_sent,
    )


# ---------------------------------------------------------------------------
# Bulk Employee Import (CSV)
# ---------------------------------------------------------------------------

class ImportRowResult(BaseModel):
    row: int
    full_name: str
    cpf: str
    email: str
    status: str  # created | existing | invalid | failed
    error: str | None = None


class ImportSummary(BaseModel):
    created: int
    existing: int
    invalid: int
    failed: int
    results: list[ImportRowResult]
    activation_emails_sent: int = 0


@router.post("/{company_id}/employees/import", response_model=ImportSummary)
async def import_employees_csv(
    company_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Bulk import employees from CSV.

    Expected columns: full_name, cpf, email, phone (optional)

    In production/staging, raw activation tokens are NEVER returned. The
    response reports delivery status only. In dev/test, tokens are sent via
    email (or silently skipped if SMTP is not configured).
    """
    tenant_id = get_current_tenant_id()

    # Verify company
    stmt = select(Company).where(
        Company.id == company_id,
        Company.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    # Validate required columns
    required = {"full_name", "cpf", "email"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must contain columns: {', '.join(sorted(required))}",
        )

    created = 0
    existing = 0
    invalid = 0
    failed = 0
    results: list[ImportRowResult] = []
    activation_emails_sent = 0

    can_return_token = _can_return_token()
    email_service = get_email_service() if not can_return_token else None

    for i, row in enumerate(reader, start=2):  # row 1 is header
        full_name = (row.get("full_name") or "").strip()
        cpf_raw = (row.get("cpf") or "").strip()
        email_raw = (row.get("email") or "").strip()
        phone = (row.get("phone") or "").strip() or None

        if not full_name or not cpf_raw or not email_raw:
            invalid += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name or "(empty)", cpf=cpf_raw, email=email_raw,
                status="invalid", error="Missing required field",
            ))
            continue

        # Strict CPF validation
        try:
            cpf = validate_cpf(cpf_raw)
        except ValueError:
            invalid += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email_raw,
                status="invalid", error="CPF inválido",
            ))
            continue

        # Normalize email
        try:
            email = normalize_email(email_raw)
        except ValueError:
            invalid += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email_raw,
                status="invalid", error="Email inválido",
            ))
            continue

        # Check duplicate CPF (tenant-scoped)
        dup_cpf = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.cpf == cpf,
                )
            )
        ).scalar_one_or_none()
        if dup_cpf:
            existing += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email,
                status="existing", error="CPF already registered",
            ))
            continue

        # Check duplicate email (tenant-scoped, case-insensitive via normalization)
        dup_email = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.email == email,
                )
            )
        ).scalar_one_or_none()
        if dup_email:
            existing += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email,
                status="existing", error="Email already registered",
            ))
            continue

        try:
            user = User(
                tenant_id=tenant_id,
                email=email,
                cpf=cpf,
                full_name=full_name,
                password_hash=None,
                role=UserRole.STUDENT,
                is_active=False,
            )
            db.add(user)
            await db.flush()

            student = Student(
                tenant_id=tenant_id,
                user_id=user.id,
                cpf=cpf,
                phone=phone,
                company_id=company_id,
                company=company.trade_name or company.legal_name,
            )
            db.add(student)
            await db.flush()

            raw_token, _ = await OneTimeTokenService.create(
                db, str(user.id), "activation", ttl_hours=168,
            )

            # In production/staging: send activation email, NEVER expose token.
            if not can_return_token and email_service:
                try:
                    await email_service.send_account_activation(
                        to=user.email,
                        activation_token=raw_token,
                        frontend_url=settings.FRONTEND_URL,
                        tenant_name="Plataforma",
                    )
                    activation_emails_sent += 1
                except EmailServiceError:
                    pass  # Don't fail the import if email fails

            created += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email,
                status="created",
            ))
        except Exception as e:  # noqa: BLE001
            failed += 1
            results.append(ImportRowResult(
                row=i, full_name=full_name, cpf=cpf_raw, email=email,
                status="failed", error=str(e),
            ))

    await db.commit()

    return ImportSummary(
        created=created,
        existing=existing,
        invalid=invalid,
        failed=failed,
        results=results,
        activation_emails_sent=activation_emails_sent,
    )
