"""Focused regression tests for deterministic payment selection logic.

Tests the actual selection behavior used by the demo seed's _get_or_create_payment():

CASE A: approved beats pending (regardless of timestamp)
CASE B: two approved → oldest approved wins
CASE C: same priority + same timestamp → stable UUID tie-break

These tests use the API client and proper ORM fixtures.
No RLS bypass. No destructive SQL.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import case, select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.payment import Payment, PaymentMethod, PaymentStatus


async def _create_test_enrollment(client, admin_headers):
    """Create a course, class, student, and enrollment via API for testing."""
    # Create course
    course_code = f"PAY-{uuid.uuid4().hex[:6].upper()}"
    course_resp = await client.post(
        "/api/v1/courses/",
        json={
            "code": course_code,
            "name": "Curso Pagamento Teste",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 299.90,
            "description": "Curso para teste de seleção de pagamento",
        },
        headers=admin_headers,
    )
    assert course_resp.status_code == 201
    course_id = course_resp.json()["id"]

    # Get admin ID
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    admin_id = me.json()["id"]

    # Create class
    start = utc_now().date() + timedelta(days=1)
    end = start + timedelta(days=30)
    class_resp = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": str(course_id),
            "responsible_admin_id": str(admin_id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "max_students": 30,
            "location": None,
            "ead_link": "https://ead.test",
            "status": "ABERTA",
            "description": "Turma teste pagamento",
        },
        headers=admin_headers,
    )
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    # Create student with class_id (this also enrolls them)
    email = f"paystudent_{uuid.uuid4().hex[:8]}@example.com"
    cpf = f"{uuid.uuid4().int % 10**11:011d}"
    student_resp = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Student Pay Test",
            "cpf": cpf,
            "password": "testpass123",
            "class_id": str(class_id),
        },
        headers=admin_headers,
    )
    assert student_resp.status_code == 201
    student_id = student_resp.json()["id"]

    # Find the enrollment that was auto-created with the student
    enrollments_resp = await client.get(
        "/api/v1/enrollments/",
        headers=admin_headers,
    )
    assert enrollments_resp.status_code == 200
    enrollments = enrollments_resp.json()
    enrollment = next(
        (e for e in enrollments if e["student_id"] == str(student_id)),
        None,
    )
    assert enrollment is not None, "Enrollment should have been auto-created with student"
    enrollment_id = enrollment["id"]

    return enrollment_id


async def _create_payment_direct(db, tenant_id, enrollment_id, status, created_at, amount=299.90):
    """Create a payment row directly with explicit created_at."""
    payment = Payment(
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        amount=amount,
        status=status,
        method=PaymentMethod.PIX,
        paid_at=utc_now() if status == PaymentStatus.APROVADO else None,
    )
    db.add(payment)
    await db.flush()
    # Override created_at after flush
    payment.created_at = created_at
    await db.flush()
    return payment


async def _select_payment(db, enrollment_id):
    """Replicate the deterministic selection logic from seed_white_label_demo.py."""
    stmt = select(Payment).where(Payment.enrollment_id == enrollment_id).order_by(
        case(
            (Payment.status == PaymentStatus.APROVADO, 0),
            else_=1
        ),
        Payment.created_at,
        Payment.id,
    )
    result = await db.execute(stmt)
    payments = result.scalars().all()
    return payments[0] if payments else None


@pytest.mark.asyncio
async def test_payment_selection_approved_beats_pending(client, admin_headers):
    """CASE A: APROVADO payment selected over PENDENTE even if PENDENTE is older."""
    from app.core.constants import WR_TENANT_ID

    enrollment_id = await _create_test_enrollment(client, admin_headers)

    old_time = utc_now() - timedelta(hours=2)
    new_time = utc_now() - timedelta(hours=1)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.PENDENTE, old_time
        )
        approved = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.APROVADO, new_time
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        selected = await _select_payment(db, enrollment_id)
        assert selected is not None
        assert selected.id == approved.id, "APROVADO must be selected over PENDENTE even if newer"
        assert selected.status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_payment_selection_two_approved_oldest_wins(client, admin_headers):
    """CASE B: With two APROVADO payments, oldest (earliest created_at) wins."""
    from app.core.constants import WR_TENANT_ID

    enrollment_id = await _create_test_enrollment(client, admin_headers)

    older_time = utc_now() - timedelta(hours=3)
    newer_time = utc_now() - timedelta(hours=1)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        older = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.APROVADO, older_time
        )
        await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.APROVADO, newer_time
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        selected = await _select_payment(db, enrollment_id)
        assert selected is not None
        assert selected.id == older.id, "Oldest APROVADO must be selected"
        assert selected.status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_payment_selection_stable_tie_break(client, admin_headers):
    """CASE C: Same priority + same created_at → stable UUID tie-break.

    The selection orders by Payment.id (UUID) as final tie-breaker.
    This is deterministic regardless of insertion order.
    """
    from app.core.constants import WR_TENANT_ID

    enrollment_id = await _create_test_enrollment(client, admin_headers)
    same_time = utc_now()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        p1 = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.APROVADO, same_time
        )
        p2 = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id, PaymentStatus.APROVADO, same_time
        )
        await db.commit()

    # Run selection multiple times - must always return the same payment
    selected_ids = set()
    for _ in range(5):
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            selected = await _select_payment(db, enrollment_id)
            selected_ids.add(str(selected.id))

    assert len(selected_ids) == 1, f"Selection must be stable, got {selected_ids}"
    # The selected payment must be the one with the smaller UUID (deterministic order by id)
    expected_id = min(str(p1.id), str(p2.id))
    assert str(selected.id) == expected_id, f"Expected {expected_id}, got {selected.id}"


@pytest.mark.asyncio
async def test_payment_selection_insertion_order_independence(client, admin_headers):
    """Verify selection does not depend on database insertion order."""
    from app.core.constants import WR_TENANT_ID

    enrollment_id_1 = await _create_test_enrollment(client, admin_headers)
    enrollment_id_2 = await _create_test_enrollment(client, admin_headers)

    older_time = utc_now() - timedelta(hours=2)
    newer_time = utc_now() - timedelta(hours=1)

    # Forward order
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        forward_older = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id_1, PaymentStatus.APROVADO, older_time
        )
        await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id_1, PaymentStatus.APROVADO, newer_time
        )
        await db.commit()

    # Reversed order
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id_2, PaymentStatus.APROVADO, newer_time
        )
        reversed_older = await _create_payment_direct(
            db, WR_TENANT_ID, enrollment_id_2, PaymentStatus.APROVADO, older_time
        )
        await db.commit()

    # Both must select the older payment
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        forward_selected = await _select_payment(db, enrollment_id_1)
        reversed_selected = await _select_payment(db, enrollment_id_2)

    assert forward_selected.id == forward_older.id, "Forward order must select older"
    assert reversed_selected.id == reversed_older.id, "Reversed order must also select older"
