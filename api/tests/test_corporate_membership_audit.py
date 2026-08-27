import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.company import Company
from app.models.student import Student
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_offboarding_reason_is_preserved_in_membership_history(client, admin_headers):
    company_id = uuid.uuid4()
    student_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            id=company_id,
            tenant_id=WR_TENANT_ID,
            legal_name="Empresa Auditável Ltda",
            cnpj="11222333000181",
            status="ACTIVE",
        )
        user = User(
            id=user_id,
            tenant_id=WR_TENANT_ID,
            email=f"audit-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Colaborador Auditável",
            cpf="52998224725",
            password_hash=hash_password("test-password-123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        student = Student(
            id=student_id,
            tenant_id=WR_TENANT_ID,
            user_id=user_id,
            cpf="52998224725",
            company_id=company_id,
            company="Empresa Auditável Ltda",
        )
        db.add_all([company, user, student])
        await db.commit()

    offboard = await client.post(
        f"/api/v1/corporate/companies/{company_id}/employees/{student_id}/offboard",
        json={
            "deactivate_account": False,
            "cancel_active_corporate_enrollments": True,
        },
        headers=admin_headers,
    )
    assert offboard.status_code == 200
    assert offboard.json()["offboarded"] is True

    annotate = await client.patch(
        f"/api/v1/corporate/companies/{company_id}/employees/{student_id}/link-events/latest",
        json={"reason": "Encerramento do vínculo com a empresa contratante"},
        headers=admin_headers,
    )
    assert annotate.status_code == 200
    event = annotate.json()
    assert event["action"] == "UNLINKED"
    assert event["previous_company_id"] == str(company_id)
    assert event["company_id"] is None
    assert event["reason"] == "Encerramento do vínculo com a empresa contratante"
    assert event["actor_user_id"] is not None

    history = await client.get(
        f"/api/v1/corporate/companies/{company_id}/link-events",
        headers=admin_headers,
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["student_id"] == str(student_id)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        student = await db.get(Student, student_id)
        assert student.company_id is None
        user = await db.get(User, user_id)
        assert user.is_active is True
