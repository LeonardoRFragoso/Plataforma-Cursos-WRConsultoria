"""
Seed data para certificados.
Gera um certificado para uma matrícula concluída.
"""

import uuid

from sqlalchemy import select

from app.models.certificate import Certificate
from app.models.enrollment import Enrollment, EnrollmentStatus


def generate_certificate_number() -> str:
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"


def generate_validation_code() -> str:
    return f"{uuid.uuid4().hex[:16].upper()}"


async def seed_certificates(db):
    """Popula o banco com certificados de teste."""
    print("\n🏆 Populando certificados...")

    stmt = select(Enrollment).where(Enrollment.status == EnrollmentStatus.CONCLUIDA)
    result = await db.execute(stmt)
    concluded_enrollment = result.scalar_one_or_none()

    if not concluded_enrollment:
        print("✗ Nenhuma matrícula concluída encontrada, pulando certificados")
        return

    # Verificar se já existe certificado
    stmt = select(Certificate).where(Certificate.enrollment_id == concluded_enrollment.id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        print(f"✓ Certificado para matrícula {concluded_enrollment.id} já existe")
        return

    certificate = Certificate(
        enrollment_id=concluded_enrollment.id,
        certificate_number=generate_certificate_number(),
        validation_code=generate_validation_code(),
    )
    db.add(certificate)

    await db.commit()
    await db.refresh(certificate)
    print(f"✓ Certificado {certificate.certificate_number} criado (validação: {certificate.validation_code})")
    print("\n✓ Seed de certificados concluído!")
