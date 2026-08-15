import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.enrollments import purchase_enrollment
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import EnrollmentStatus
from app.models.payment import PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentPurchaseRequest


async def _seed_purchase_data():
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        student_user = User(
            email=f"student_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Student",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Comprável",
            category="Segurança",
            carga_horaria=40,
            modality="PRESENCIAL",
            price=150.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)

        await db.flush()

        cls = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cls)

        student = Student(
            user_id=student_user.id,
            cpf="52988744005",
            phone="(11) 99999-9999",
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)

        await db.commit()

        return course.id, cls.id, student.id, student_user.id


@pytest.mark.asyncio
async def test_purchase_enrollment_creates_payment():
    course_id, class_id, student_id, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)

    assert result.enrollment.student_id == student_id
    assert result.enrollment.class_id == class_id
    assert result.enrollment.status == EnrollmentStatus.PENDENTE
    assert result.payment.status == PaymentStatus.PENDENTE
    assert result.payment.amount == 150.0
    assert result.payment.method.value == "BOLETO"


@pytest.mark.asyncio
async def test_purchase_enrollment_is_idempotent():
    course_id, _, _, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)

        first = await purchase_enrollment(data, db, current_user)
        second = await purchase_enrollment(data, db, current_user)

    assert first.enrollment.id == second.enrollment.id
    assert first.payment.id == second.payment.id


@pytest.mark.asyncio
async def test_purchase_enrollment_rejects_non_student():
    course_id, *_ = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(uuid.uuid4()), "role": "admin"}
        data = EnrollmentPurchaseRequest(course_id=course_id)

        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_purchase_enrollment_course_not_found():
    _, _, _, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)
        assert exc.value.status_code == 404


async def _seed_purchase_data_with_extra_class(*, first_class_status=ClassStatus.ABERTA):
    """Cria curso, aluno, turma antiga (status custom) e turma nova ABERTA."""
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        student_user = User(
            email=f"student_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Student",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Idempotência Cross-Class",
            category="Segurança",
            carga_horaria=40,
            modality="PRESENCIAL",
            price=200.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)

        await db.flush()

        old_class = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=30),
            max_students=20,
            status=first_class_status,
            tenant_id=WR_TENANT_ID,
        )
        db.add(old_class)

        new_class = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(new_class)

        student = Student(
            user_id=student_user.id,
            cpf="52998744005",
            phone="(11) 99999-9999",
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)

        await db.commit()
        return course.id, old_class.id, new_class.id, student.id, student_user.id


@pytest.mark.asyncio
async def test_purchase_idempotent_confirmed_in_old_class_no_duplicate():
    """CONFIRMADA em turma antiga + nova turma ABERTA -> purchase não cria duplicata."""
    from app.models.enrollment import Enrollment

    course_id, old_class_id, new_class_id, student_id, user_id = (
        await _seed_purchase_data_with_extra_class()
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        existing = Enrollment(
            student_id=student_id,
            class_id=old_class_id,
            price=200.0,
            status=EnrollmentStatus.CONFIRMADA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        existing_id = existing.id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)

    # Retorna a matrícula existente, não cria nova na turma nova
    assert result.enrollment.id == existing_id
    assert result.enrollment.class_id == old_class_id

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as _select

        count = (
            await db.execute(
                _select(Enrollment).where(
                    Enrollment.student_id == student_id,
                    Enrollment.class_id == new_class_id,
                )
            )
        ).scalars().all()
        assert len(count) == 0  # nenhuma duplicata na turma nova


@pytest.mark.asyncio
async def test_purchase_idempotent_concluded_in_old_class_no_duplicate():
    """CONCLUIDA em turma antiga + nova turma ABERTA -> purchase não cria duplicata."""
    from app.models.enrollment import Enrollment

    course_id, old_class_id, new_class_id, student_id, user_id = (
        await _seed_purchase_data_with_extra_class()
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        existing = Enrollment(
            student_id=student_id,
            class_id=old_class_id,
            price=200.0,
            status=EnrollmentStatus.CONCLUIDA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        existing_id = existing.id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)

    assert result.enrollment.id == existing_id
    assert result.enrollment.class_id == old_class_id

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as _select

        count = (
            await db.execute(
                _select(Enrollment).where(
                    Enrollment.student_id == student_id,
                    Enrollment.class_id == new_class_id,
                )
            )
        ).scalars().all()
        assert len(count) == 0


@pytest.mark.asyncio
async def test_purchase_idempotent_pending_reuses_existing():
    """PENDENTE em turma antiga -> purchase reutiliza a mesma matrícula/pagamento."""
    from app.models.enrollment import Enrollment

    course_id, old_class_id, _, student_id, user_id = (
        await _seed_purchase_data_with_extra_class()
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        existing = Enrollment(
            student_id=student_id,
            class_id=old_class_id,
            price=200.0,
            status=EnrollmentStatus.PENDENTE,
            tenant_id=WR_TENANT_ID,
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        existing_id = existing.id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        first = await purchase_enrollment(data, db, current_user)
        second = await purchase_enrollment(data, db, current_user)

    assert first.enrollment.id == existing_id
    assert second.enrollment.id == existing_id
    assert first.payment.id == second.payment.id


@pytest.mark.asyncio
async def test_purchase_cancelled_allows_new_purchase_in_new_class():
    """CANCELADA em turma antiga -> permite nova compra em turma ABERTA."""
    from app.models.enrollment import Enrollment

    course_id, old_class_id, new_class_id, student_id, user_id = (
        await _seed_purchase_data_with_extra_class(first_class_status=ClassStatus.CONCLUIDA)
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        cancelled = Enrollment(
            student_id=student_id,
            class_id=old_class_id,
            price=200.0,
            status=EnrollmentStatus.CANCELADA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cancelled)
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)

    # Nova matrícula criada na turma nova (regra explícita de abandono)
    assert result.enrollment.class_id == new_class_id
    assert result.enrollment.status == EnrollmentStatus.PENDENTE
    assert result.payment.amount == 200.0


@pytest.mark.asyncio
async def test_purchase_respects_class_capacity():
    """Capacidade máxima não pode ser ultrapassada."""
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Capacidade",
            category="Segurança",
            carga_horaria=40,
            modality="PRESENCIAL",
            price=100.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)
        await db.flush()

        cls = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
            max_students=1,  # capacidade 1
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cls)

        # Primeiro aluno
        u1 = User(
            email=f"s1_{uuid.uuid4().hex[:6]}@test.com",
            full_name="S1",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(u1)
        await db.flush()
        s1 = Student(
            user_id=u1.id,
            cpf="11122233344",
            phone="(11) 1",
            tenant_id=WR_TENANT_ID,
        )
        db.add(s1)

        # Segundo aluno
        u2 = User(
            email=f"s2_{uuid.uuid4().hex[:6]}@test.com",
            full_name="S2",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(u2)
        await db.flush()
        s2 = Student(
            user_id=u2.id,
            cpf="22233344455",
            phone="(11) 2",
            tenant_id=WR_TENANT_ID,
        )
        db.add(s2)

        await db.commit()
        course_id = course.id
        u1_id, u2_id = u1.id, u2.id

    # Primeiro aluno compra -> ocupa a única vaga
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(u1_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)
        assert result.enrollment.status == EnrollmentStatus.PENDENTE

    # Segundo aluno compra -> sem vagas
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(u2_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)
        assert exc.value.status_code == 400
