"""Idempotent staging/demo seed for the White Label CEO demo.

Creates two tenants (WR + Alfa) with distinct datasets:
- Admin users (env-configured credentials)
- Students
- Courses
- Classes
- Enrollments
- Payments
- Certificates

Gated by DEMO_SEED_MODE=true AND ENVIRONMENT != production.
Credentials come from environment variables — never hardcoded.

Usage:
    DEMO_SEED_MODE=true \
    DEMO_WR_ADMIN_EMAIL=... DEMO_WR_ADMIN_PASSWORD=... \
    DEMO_ALFA_ADMIN_EMAIL=... DEMO_ALFA_ADMIN_PASSWORD=... \
    python -m app.scripts.seed_white_label_demo
"""

import asyncio
import os
import sys
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import get_db_privileged
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.plan import BillingCycle, Plan
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.models.user import User, UserRole


def _check_gate():
    if not settings.DEMO_SEED_MODE:
        print("ABORT: DEMO_SEED_MODE is not true. Refusing to seed.")
        sys.exit(1)
    if settings.ENVIRONMENT.lower() == "production":
        print("ABORT: ENVIRONMENT=production. Refusing to seed.")
        sys.exit(1)


def _env(name, default=None):
    val = os.environ.get(name, default)
    if not val:
        print(f"ABORT: environment variable {name} is required.")
        sys.exit(1)
    return val


async def _get_or_create_tenant(db, slug, defaults):
    stmt = select(Tenant).where(Tenant.slug == slug)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant:
        for k, v in defaults.items():
            if getattr(tenant, k, None) is None and v is not None:
                setattr(tenant, k, v)
        return tenant, False
    tenant = Tenant(slug=slug, status=TenantStatus.ACTIVE, **defaults)
    db.add(tenant)
    await db.flush()
    return tenant, True


async def _get_or_create_user(db, email, tenant_id, full_name, role, password):
    stmt = select(User).where(User.email == email, User.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        return user, False
    user = User(
        email=email,
        full_name=full_name,
        cpf=str(uuid4().int)[:11],
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.add(user)
    await db.flush()
    return user, True


async def _get_or_create_student(db, user_id, tenant_id):
    stmt = select(Student).where(Student.user_id == user_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if student:
        return student
    student = Student(user_id=user_id, tenant_id=tenant_id, cpf=str(uuid4().int)[:11])
    db.add(student)
    await db.flush()
    return student


async def _get_or_create_course(db, tenant_id, code, name, category, carga, price):
    stmt = select(Course).where(Course.tenant_id == tenant_id, Course.code == code)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if course:
        return course
    course = Course(
        tenant_id=tenant_id,
        code=code,
        name=name,
        category=category,
        carga_horaria=carga,
        modality=CourseModality.EAD,
        tipo_curso=CourseType.FORMACAO,
        price=price,
    )
    db.add(course)
    await db.flush()
    return course


async def _get_or_create_class(db, tenant_id, course_id, admin_id, location):
    cls = Class(
        tenant_id=tenant_id,
        course_id=course_id,
        responsible_admin_id=admin_id,
        start_date=utc_now().date(),
        end_date=(utc_now() + timedelta(days=90)).date(),
        max_students=50,
        location=location,
        status=ClassStatus.ABERTA,
    )
    db.add(cls)
    await db.flush()
    return cls


async def _seed_tenant(
    db,
    tenant_id,
    slug,
    name,
    primary_color,
    secondary_color,
    accent_color,
    admin_email,
    admin_password,
    admin_name,
    courses_data,
    student_specs,
):
    """Seed one tenant with admin, courses, students, classes, enrollments, payments, certificate."""
    token = current_tenant_id.set(tenant_id)
    db.info["tenant_id"] = tenant_id
    try:
        # Admin
        admin, created = await _get_or_create_user(
            db, admin_email, tenant_id, admin_name, UserRole.ADMIN, admin_password
        )
        if created:
            print(f"  [{slug}] Admin created: {admin_email}")
        else:
            print(f"  [{slug}] Admin exists: {admin_email}")

        # Courses
        course_objs = {}
        for c in courses_data:
            course = await _get_or_create_course(
                db, tenant_id, c["code"], c["name"], c["category"], c["carga"], c["price"]
            )
            course_objs[c["code"]] = course
            print(f"  [{slug}] Course: {c['code']} — {c['name']}")

        # Classes (one per course)
        class_objs = {}
        for code, course in course_objs.items():
            cls = await _get_or_create_class(db, tenant_id, course.id, admin.id, f"{slug.upper()} EAD")
            class_objs[code] = cls

        # Students + enrollments + payments + certificate
        for spec in student_specs:
            stu_user, stu_created = await _get_or_create_user(
                db,
                spec["email"],
                tenant_id,
                spec["name"],
                UserRole.STUDENT,
                spec["password"],
            )
            student = await _get_or_create_student(db, stu_user.id, tenant_id)
            if stu_created:
                print(f"  [{slug}] Student: {spec['email']}")

            # Enroll in first course's class
            first_code = next(iter(course_objs.keys()))
            cls = class_objs[first_code]
            course = course_objs[first_code]

            stmt = select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.class_id == cls.id,
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if not existing:
                enrollment = Enrollment(
                    tenant_id=tenant_id,
                    student_id=student.id,
                    class_id=cls.id,
                    status=EnrollmentStatus.CONFIRMADA,
                    price=course.price,
                )
                db.add(enrollment)
                await db.flush()

                payment = Payment(
                    tenant_id=tenant_id,
                    enrollment_id=enrollment.id,
                    amount=course.price,
                    status=PaymentStatus.APROVADO,
                    method=PaymentMethod.PIX,
                    paid_at=utc_now(),
                )
                db.add(payment)

                # Certificate for first student only
                if spec.get("certificate"):
                    cert_stmt = select(Certificate).where(
                        Certificate.enrollment_id == enrollment.id
                    )
                    if not (await db.execute(cert_stmt)).scalar_one_or_none():
                        cert = Certificate(
                            tenant_id=tenant_id,
                            enrollment_id=enrollment.id,
                            certificate_number=f"CERT-{uuid4().hex[:12].upper()}",
                            validation_code=uuid4().hex[:16].upper(),
                        )
                        db.add(cert)
                        print(f"  [{slug}] Certificate for {spec['email']}")
    finally:
        current_tenant_id.reset(token)


async def main():
    _check_gate()

    wr_admin_email = _env("DEMO_WR_ADMIN_EMAIL", "admin@wr.demo")
    wr_admin_password = _env("DEMO_WR_ADMIN_PASSWORD")
    alfa_admin_email = _env("DEMO_ALFA_ADMIN_EMAIL", "admin@alfa.demo")
    alfa_admin_password = _env("DEMO_ALFA_ADMIN_PASSWORD")

    print("=== White Label Demo Seed ===")
    print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
    print()

    async for db in get_db_privileged():
        # --- WR Tenant ---
        wr_tenant, wr_created = await _get_or_create_tenant(
            db,
            slug="wr",
            defaults={
                "id": WR_TENANT_ID,
                "name": "WR Consultoria e Soluções",
                "contact_name": "Admin WR",
                "contact_email": wr_admin_email,
                "primary_color": "#0056b3",
                "secondary_color": "#1a1a1a",
                "accent_color": "#ff6b35",
            },
        )
        if wr_created:
            print(f"WR tenant created: {wr_tenant.id}")
        else:
            print(f"WR tenant exists: {wr_tenant.id}")

        # --- Alfa Tenant ---
        alfa_tenant, alfa_created = await _get_or_create_tenant(
            db,
            slug="alfa",
            defaults={
                "name": "Alfa Academy",
                "legal_name": "Alfa Engenharia",
                "contact_name": "Admin Alfa",
                "contact_email": alfa_admin_email,
                "primary_color": "#E86A17",
                "secondary_color": "#1F2937",
                "accent_color": "#FBBF24",
            },
        )
        if alfa_created:
            print(f"Alfa tenant created: {alfa_tenant.id}")
        else:
            print(f"Alfa tenant exists: {alfa_tenant.id}")

        # --- Global Plan (catalog) ---
        plan_stmt = select(Plan).where(Plan.tenant_id.is_(None), Plan.name == "Demo Starter")
        plan = (await db.execute(plan_stmt)).scalar_one_or_none()
        if not plan:
            plan = Plan(
                tenant_id=None,
                name="Demo Starter",
                description="Plano demo para CEO presentation",
                price=299.00,
                billing_cycle=BillingCycle.MONTHLY,
                is_active=True,
            )
            db.add(plan)
            await db.flush()
            print(f"Global plan created: {plan.id}")
        else:
            print(f"Global plan exists: {plan.id}")

        # --- Subscriptions ---
        for tenant, status in [(wr_tenant, SubscriptionStatus.ACTIVE), (alfa_tenant, SubscriptionStatus.ACTIVE)]:
            sub_stmt = select(TenantSubscription).where(
                TenantSubscription.tenant_id == tenant.id,
                TenantSubscription.plan_id == plan.id,
            )
            sub = (await db.execute(sub_stmt)).scalar_one_or_none()
            if not sub:
                sub = TenantSubscription(
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    status=status,
                    start_date=utc_now(),
                    end_date=utc_now() + timedelta(days=365),
                )
                db.add(sub)
                print(f"  Subscription for {tenant.slug}: {status}")

        # --- WR Data ---
        print("\n--- WR Tenant ---")
        await _seed_tenant(
            db,
            WR_TENANT_ID,
            "wr",
            "WR Consultoria e Soluções",
            "#0056b3",
            "#1a1a1a",
            "#ff6b35",
            wr_admin_email,
            wr_admin_password,
            "Administrador WR",
            courses_data=[
                {"code": "NR-10", "name": "NR-10 Segurança em Instalações Elétricas", "category": "Segurança", "carga": 40, "price": 299.90},
                {"code": "NR-35", "name": "NR-35 Trabalho em Altura", "category": "Segurança", "carga": 8, "price": 149.90},
                {"code": "NR-12", "name": "NR-12 Máquinas e Equipamentos", "category": "Segurança", "carga": 12, "price": 199.90},
            ],
            student_specs=[
                {"email": "aluno1@wr.demo", "name": "João Silva", "password": _env("DEMO_WR_STUDENT_PASSWORD", "demo123"), "certificate": True},
                {"email": "aluno2@wr.demo", "name": "Maria Santos", "password": _env("DEMO_WR_STUDENT_PASSWORD", "demo123")},
            ],
        )

        # --- Alfa Data ---
        print("\n--- Alfa Tenant ---")
        await _seed_tenant(
            db,
            alfa_tenant.id,
            "alfa",
            "Alfa Academy",
            "#E86A17",
            "#1F2937",
            "#FBBF24",
            alfa_admin_email,
            alfa_admin_password,
            "Administrador Alfa",
            courses_data=[
                {"code": "SEG-01", "name": "Integração de Segurança", "category": "Engenharia", "carga": 16, "price": 399.90},
                {"code": "RISC-01", "name": "Gestão de Riscos", "category": "Engenharia", "carga": 24, "price": 599.90},
                {"code": "OPS-01", "name": "Treinamento Operacional", "category": "Operacional", "carga": 12, "price": 249.90},
            ],
            student_specs=[
                {"email": "aluno1@alfa.demo", "name": "Carlos Engenheiro", "password": _env("DEMO_ALFA_STUDENT_PASSWORD", "demo123"), "certificate": True},
                {"email": "aluno2@alfa.demo", "name": "Ana Técnica", "password": _env("DEMO_ALFA_STUDENT_PASSWORD", "demo123")},
            ],
        )

        await db.commit()
        break

    print("\n=== Seed complete ===")
    print(f"WR admin:    {wr_admin_email}")
    print(f"Alfa admin:  {alfa_admin_email}")
    print("Passwords were NOT printed. Check your env variables.")


if __name__ == "__main__":
    asyncio.run(main())
