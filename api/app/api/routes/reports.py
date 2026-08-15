import io

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment
from app.models.payment import Payment
from app.models.student import Student
from app.services.export_service import ExportService

router = APIRouter()


def _format_enrollment(e: Enrollment) -> dict:
    return {
        "id": str(e.id),
        "student_id": str(e.student_id),
        "class_id": str(e.class_id),
        "price": e.price,
        "status": e.status,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _format_payment(p: Payment) -> dict:
    return {
        "id": str(p.id),
        "enrollment_id": str(p.enrollment_id),
        "amount": p.amount,
        "status": p.status,
        "method": p.method,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _format_student(s: Student) -> dict:
    return {
        "id": str(s.id),
        "user_id": str(s.user_id),
        "cpf": s.cpf,
        "phone": s.phone,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _format_certificate(c: Certificate) -> dict:
    return {
        "id": str(c.id),
        "enrollment_id": str(c.enrollment_id),
        "certificate_number": c.certificate_number,
        "validation_code": c.validation_code,
        "issued_at": c.issued_at,
        "pdf_path": c.pdf_path,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


COLUMNS = {
    "enrollments": ["id", "student_id", "class_id", "price", "status", "created_at", "updated_at"],
    "payments": ["id", "enrollment_id", "amount", "status", "method", "created_at", "updated_at"],
    "students": ["id", "user_id", "cpf", "phone", "created_at", "updated_at"],
    "certificates": [
        "id",
        "enrollment_id",
        "certificate_number",
        "validation_code",
        "issued_at",
        "pdf_path",
        "created_at",
        "updated_at",
    ],
}


async def _fetch_enrollments(db: AsyncSession, tenant_id):
    result = await db.execute(select(Enrollment).where(Enrollment.tenant_id == tenant_id))
    rows = [_format_enrollment(e) for e in result.scalars().all()]
    return COLUMNS["enrollments"], rows


async def _fetch_payments(db: AsyncSession, tenant_id):
    result = await db.execute(select(Payment).where(Payment.tenant_id == tenant_id))
    rows = [_format_payment(p) for p in result.scalars().all()]
    return COLUMNS["payments"], rows


async def _fetch_students(db: AsyncSession, tenant_id):
    result = await db.execute(select(Student).where(Student.tenant_id == tenant_id))
    rows = [_format_student(s) for s in result.scalars().all()]
    return COLUMNS["students"], rows


async def _fetch_certificates(db: AsyncSession, tenant_id):
    result = await db.execute(select(Certificate).where(Certificate.tenant_id == tenant_id))
    rows = [_format_certificate(c) for c in result.scalars().all()]
    return COLUMNS["certificates"], rows


FETCHERS = {
    "enrollments": _fetch_enrollments,
    "payments": _fetch_payments,
    "students": _fetch_students,
    "certificates": _fetch_certificates,
}


@router.get("/{resource}/export")
async def export_data(
    resource: str,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    if resource not in FETCHERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    if format not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'csv' or 'xlsx'",
        )

    tenant_id = get_current_tenant_id()
    columns, rows = await FETCHERS[resource](db, tenant_id)

    if format == "csv":
        content = ExportService.to_csv(rows, columns)
        media_type = "text/csv; charset=utf-8"
    else:
        content = ExportService.to_xlsx(rows, columns)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    timestamp = utc_now().strftime("%Y%m%d%H%M%S")
    filename = f"{resource}_{timestamp}.{format}"
    return _stream_bytes(content, media_type, filename)


def _stream_bytes(content: bytes, media_type: str, filename: str):
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
