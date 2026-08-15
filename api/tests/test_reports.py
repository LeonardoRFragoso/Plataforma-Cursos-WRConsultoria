import pytest

from app.api.routes.reports import export_data
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.export_service import ExportService


def test_export_csv():
    rows = [
        {"id": "1", "name": "Alice", "value": 10.5},
        {"id": "2", "name": "Bob", "value": 20.0},
    ]
    content = ExportService.to_csv(rows, ["id", "name", "value"])
    text = content.decode("utf-8-sig")
    assert "id,name,value" in text
    assert "Alice" in text
    assert "Bob" in text


def test_export_xlsx():
    rows = [
        {"id": "1", "name": "Alice", "value": 10.5},
        {"id": "2", "name": "Bob", "value": 20.0},
    ]
    content = ExportService.to_xlsx(rows, ["id", "name", "value"])
    assert content.startswith(b"PK")


def test_export_empty_csv():
    content = ExportService.to_csv([], ["id", "name"])
    text = content.decode("utf-8-sig")
    assert "id,name" in text


def test_export_empty_xlsx():
    content = ExportService.to_xlsx([], ["id", "name"])
    assert content.startswith(b"PK")


@pytest.mark.asyncio
async def test_export_students_csv():
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID

            user = User(
                email="student-export@test.com",
                full_name="Student Export",
                password_hash=hash_password("student123"),
                role=UserRole.STUDENT,
                is_active=True,
                tenant_id=WR_TENANT_ID,
            )
            db.add(user)
            await db.flush()

            student = Student(
                user_id=user.id,
                cpf="52988744005",
                phone="(11) 99999-9999",
                tenant_id=WR_TENANT_ID,
            )
            db.add(student)
            await db.commit()

        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            response = await export_data(
                "students",
                "csv",
                db,
                {"user_id": str(user.id), "role": "admin"},
            )
            assert response.media_type == "text/csv; charset=utf-8"
            body = b"".join([chunk async for chunk in response.body_iterator])
            assert b"52988744005" in body
    finally:
        current_tenant_id.reset(token)
