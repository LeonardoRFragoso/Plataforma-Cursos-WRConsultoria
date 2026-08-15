import uuid

import pytest
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal, engine
from app.core.migration_reconcile import reconcile_enrollments
from app.core.utils import utc_now
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole


@pytest.fixture
async def drop_uq():
    """Remove a constraint única para permitir inserção de duplicatas nos testes."""
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text(
                    "ALTER TABLE enrollments "
                    "DROP CONSTRAINT IF EXISTS uq_enrollment_student_class, "
                    "DROP CONSTRAINT IF EXISTS uq_enrollment_tenant_student_class"
                )
            )
        )


async def _seed_base(session):
    """Cria admin, curso e turma."""
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Admin",
        cpf=f"{uuid.uuid4().int % 10**11:011d}",
        password_hash="x",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.flush()

    course = Course(
        code=f"CUR-{uuid.uuid4().hex[:6].upper()}",
        name="Curso de Teste",
        category="Segurança",
        carga_horaria=40,
        price=100.0,
    )
    session.add(course)
    await session.flush()

    today = utc_now().date()
    class_obj = Class(
        course_id=course.id,
        responsible_admin_id=admin.id,
        start_date=today,
        end_date=today,
        max_students=20,
        status=ClassStatus.ABERTA,
    )
    session.add(class_obj)
    await session.flush()

    return admin, course, class_obj


async def _make_student(session, class_obj, email=None, cpf=None):
    email = email or f"student_{uuid.uuid4().hex[:8]}@example.com"
    cpf = cpf or f"{uuid.uuid4().int % 10**11:011d}"
    user = User(
        email=email,
        full_name="Aluno",
        cpf=cpf,
        password_hash="x",
        role=UserRole.STUDENT,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    student = Student(user_id=user.id, cpf=cpf)
    session.add(student)
    await session.flush()
    return student


async def test_reconcile_status_priority(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)

        student1 = await _make_student(session, class_obj)
        e1 = uuid.uuid4()
        e2 = uuid.uuid4()
        session.add(
            Enrollment(
                id=e1,
                student_id=student1.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        session.add(
            Enrollment(
                id=e2,
                student_id=student1.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
        )

        student2 = await _make_student(session, class_obj)
        e3 = uuid.uuid4()
        e4 = uuid.uuid4()
        session.add(
            Enrollment(
                id=e3,
                student_id=student2.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CANCELADA,
            )
        )
        session.add(
            Enrollment(
                id=e4,
                student_id=student2.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONCLUIDA,
            )
        )
        await session.commit()

    async with engine.begin() as conn:
        await conn.run_sync(reconcile_enrollments)

    async with AsyncSessionLocal() as session:
        remaining1 = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student1.id))
        ).scalars().all()
        assert len(remaining1) == 1
        assert remaining1[0].id == e2
        assert remaining1[0].status == EnrollmentStatus.CONFIRMADA

        remaining2 = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student2.id))
        ).scalars().all()
        assert len(remaining2) == 1
        assert remaining2[0].id == e4
        assert remaining2[0].status == EnrollmentStatus.CONCLUIDA


async def test_reconcile_preserves_payment(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)
        student = await _make_student(session, class_obj)

        e_keep = uuid.uuid4()
        e_drop = uuid.uuid4()
        session.add(
            Enrollment(
                id=e_keep,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        session.add(
            Enrollment(
                id=e_drop,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
        )
        await session.flush()
        payment = Payment(
            enrollment_id=e_keep,
            amount=100.0,
            status=PaymentStatus.PENDENTE,
            method=PaymentMethod.PIX,
        )
        session.add(payment)
        await session.commit()

    async with engine.begin() as conn:
        await conn.run_sync(reconcile_enrollments)

    async with AsyncSessionLocal() as session:
        remaining = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student.id))
        ).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == e_keep

        payments = (
            await session.execute(select(Payment).where(Payment.enrollment_id == e_keep))
        ).scalars().all()
        assert len(payments) == 1
        assert payments[0].amount == 100.0


async def test_reconcile_preserves_certificate(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)
        student = await _make_student(session, class_obj)

        e_keep = uuid.uuid4()
        e_drop = uuid.uuid4()
        session.add(
            Enrollment(
                id=e_keep,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        session.add(
            Enrollment(
                id=e_drop,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
        )
        await session.flush()
        now = utc_now()
        certificate = Certificate(
            enrollment_id=e_keep,
            certificate_number=uuid.uuid4().hex,
            validation_code=uuid.uuid4().hex,
            issued_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(certificate)
        await session.commit()

    async with engine.begin() as conn:
        await conn.run_sync(reconcile_enrollments)

    async with AsyncSessionLocal() as session:
        remaining = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student.id))
        ).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == e_keep

        certs = (
            await session.execute(select(Certificate).where(Certificate.enrollment_id == e_keep))
        ).scalars().all()
        assert len(certs) == 1


async def test_reconcile_preserves_attendance(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)
        student = await _make_student(session, class_obj)

        e_keep = uuid.uuid4()
        e_drop = uuid.uuid4()
        session.add(
            Enrollment(
                id=e_keep,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        session.add(
            Enrollment(
                id=e_drop,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
        )
        await session.flush()
        now = utc_now()
        attendance = Attendance(
            enrollment_id=e_keep,
            class_id=class_obj.id,
            attendance_date=utc_now().date(),
            present=True,
            created_at=now,
            updated_at=now,
        )
        session.add(attendance)
        await session.commit()

    async with engine.begin() as conn:
        await conn.run_sync(reconcile_enrollments)

    async with AsyncSessionLocal() as session:
        remaining = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student.id))
        ).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == e_keep

        attendances = (
            await session.execute(select(Attendance).where(Attendance.enrollment_id == e_keep))
        ).scalars().all()
        assert len(attendances) == 1


async def test_reconcile_no_duplicates(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)
        student = await _make_student(session, class_obj)

        e1 = uuid.uuid4()
        session.add(
            Enrollment(
                id=e1,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        await session.commit()

    async with engine.begin() as conn:
        await conn.run_sync(reconcile_enrollments)

    async with AsyncSessionLocal() as session:
        remaining = (
            await session.execute(select(Enrollment).where(Enrollment.student_id == student.id))
        ).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == e1


async def test_reconcile_raises_for_conflicting_history(drop_uq):
    async with AsyncSessionLocal() as session:
        _, _, class_obj = await _seed_base(session)
        student = await _make_student(session, class_obj)

        e1 = uuid.uuid4()
        e2 = uuid.uuid4()
        session.add(
            Enrollment(
                id=e1,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.PENDENTE,
            )
        )
        session.add(
            Enrollment(
                id=e2,
                student_id=student.id,
                class_id=class_obj.id,
                price=100.0,
                status=EnrollmentStatus.CONFIRMADA,
            )
        )
        await session.flush()
        now = utc_now()
        payment = Payment(
            enrollment_id=e1,
            amount=100.0,
            status=PaymentStatus.PENDENTE,
            method=PaymentMethod.PIX,
        )
        certificate = Certificate(
            enrollment_id=e2,
            certificate_number=uuid.uuid4().hex,
            validation_code=uuid.uuid4().hex,
            issued_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.add(certificate)
        await session.commit()

    with pytest.raises(RuntimeError):
        async with engine.begin() as conn:
            await conn.run_sync(reconcile_enrollments)
