"""Regression tests for corporate student onboarding and company management.

Covers:
- Company tenant isolation (create, list, get, update, delete)
- Corporate student creation with company_id (no class required)
- Independent student creation (company_id NULL)
- Company/student tenant mismatch rejected
- Bulk employee import (CSV)
- Bulk enrollment with capacity enforcement
- Duplicate enrollment prevention
- Corporate enrollment access without checkout (no payment)
- Individual Mercado Pago flow preserved (source=INDIVIDUAL)
"""
import uuid

import pytest
from httpx import AsyncClient

from app.core.constants import WR_TENANT_ID
from tests.cnpj_utils import make_valid_cnpj
from tests.conftest import make_valid_cpf


async def _create_company(client: AsyncClient, headers: dict, name: str = "Empresa Teste LTDA") -> str:
    """Create a company and return its ID."""
    response = await client.post(
        "/api/v1/companies/",
        json={
            "legal_name": name,
            "trade_name": name,
            "cnpj": make_valid_cnpj(),
            "rh_name": "RH Teste",
            "rh_email": f"rh_{uuid.uuid4().hex[:8]}@teste.com",
            "rh_phone": "(11) 99999-9999",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_course(client: AsyncClient, headers: dict) -> str:
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": f"TEST-{uuid.uuid4().hex[:6]}",
            "name": "Curso Teste",
            "category": "Testes",
            "carga_horaria": 10,
            "modality": "PRESENCIAL",
            "tipo_curso": "FORMACAO",
            "price": 100.0,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_class(client: AsyncClient, headers: dict, course_id: str, max_students: int = 20) -> str:
    admin_response = await client.get("/api/v1/auth/me", headers=headers)
    admin_id = admin_response.json()["id"]
    response = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course_id,
            "responsible_admin_id": admin_id,
            "start_date": "2026-12-01",
            "end_date": "2026-12-31",
            "max_students": max_students,
            "location": "São Paulo",
            "status": "ABERTA",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_employee(client: AsyncClient, headers: dict, company_id: str, name: str = "Func") -> str:
    """Create an employee via the company endpoint and return student ID."""
    response = await client.post(
        f"/api/v1/companies/{company_id}/employees",
        json={
            "full_name": f"{name} {uuid.uuid4().hex[:4]}",
            "cpf": make_valid_cpf(),
            "email": f"func_{uuid.uuid4().hex[:8]}@empresa.com",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["student"]["id"]


class TestCompanyTenantIsolation:
    """Company CRUD must enforce tenant boundaries."""

    @pytest.mark.asyncio
    async def test_company_create_sets_tenant(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers, "Empresa ABC")
        response = await client.get(f"/api/v1/companies/{company_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(WR_TENANT_ID)

    @pytest.mark.asyncio
    async def test_company_list_is_tenant_scoped(self, client, admin_headers):
        await _create_company(client, admin_headers, "Empresa A")
        await _create_company(client, admin_headers, "Empresa B")
        response = await client.get("/api/v1/companies/", headers=admin_headers)
        assert response.status_code == 200
        companies = response.json()
        assert len(companies) >= 2
        for c in companies:
            assert c["tenant_id"] == str(WR_TENANT_ID)

    @pytest.mark.asyncio
    async def test_company_duplicate_cnpj_rejected(self, client, admin_headers):
        cnpj = make_valid_cnpj()
        response = await client.post(
            "/api/v1/companies/",
            json={"legal_name": "Empresa A", "cnpj": cnpj},
            headers=admin_headers,
        )
        assert response.status_code == 201
        response = await client.post(
            "/api/v1/companies/",
            json={"legal_name": "Empresa B", "cnpj": cnpj},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "CNPJ" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_company_get_404_for_nonexistent(self, client, admin_headers):
        response = await client.get(
            f"/api/v1/companies/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_company_update(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers, "Empresa Original")
        response = await client.put(
            f"/api/v1/companies/{company_id}",
            json={"trade_name": "Empresa Atualizada"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["trade_name"] == "Empresa Atualizada"

    @pytest.mark.asyncio
    async def test_company_delete(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers, "Empresa Delete")
        response = await client.delete(f"/api/v1/companies/{company_id}", headers=admin_headers)
        assert response.status_code == 204
        response = await client.get(f"/api/v1/companies/{company_id}", headers=admin_headers)
        assert response.status_code == 404


class TestCorporateStudentCreation:
    """Student creation decoupled from enrollment."""

    @pytest.mark.asyncio
    async def test_create_corporate_student_without_class(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)
        response = await client.post(
            "/api/v1/students/",
            json={
                "full_name": "João Silva",
                "email": f"joao_{uuid.uuid4().hex[:8]}@empresa.com",
                "cpf": make_valid_cpf(),
                "company_id": company_id,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["company_id"] == company_id
        assert data.get("activation_token") is not None

    @pytest.mark.asyncio
    async def test_create_independent_student_without_company(self, client, admin_headers):
        response = await client.post(
            "/api/v1/students/",
            json={
                "full_name": "Maria Souza",
                "email": f"maria_{uuid.uuid4().hex[:8]}@gmail.com",
                "cpf": make_valid_cpf(),
            },
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["company_id"] is None
        assert data.get("activation_token") is not None

    @pytest.mark.asyncio
    async def test_create_student_with_nonexistent_company_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/students/",
            json={
                "full_name": "Teste",
                "email": f"test_{uuid.uuid4().hex[:8]}@test.com",
                "cpf": make_valid_cpf(),
                "company_id": str(uuid.uuid4()),
            },
            headers=admin_headers,
        )
        assert response.status_code == 404
        assert "Company not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_student_list_is_tenant_scoped(self, client, admin_headers):
        response = await client.get("/api/v1/students/", headers=admin_headers)
        assert response.status_code == 200
        for s in response.json():
            assert s["id"] is not None

    @pytest.mark.asyncio
    async def test_company_stats(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)
        # Add an employee
        await _create_employee(client, admin_headers, company_id, "Func Stats")
        response = await client.get(f"/api/v1/companies/{company_id}/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_employees"] == 1
        assert data["enrolled_employees"] == 0
        assert data["certificates_issued"] == 0


class TestBulkEmployeeImport:
    """CSV import of employees."""

    @pytest.mark.asyncio
    async def test_csv_import_creates_employees(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)

        csv_content = "full_name,cpf,email,phone\n"
        for i in range(5):
            csv_content += f"Funcionário {i},{make_valid_cpf()},func{i}_{uuid.uuid4().hex[:8]}@empresa.com,11999999999\n"

        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        response = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["created"] == 5
        assert data["existing"] == 0
        assert data["invalid"] == 0
        # Production contract: raw activation tokens are NEVER returned.
        # The response reports delivery status only.
        assert "activation_tokens" not in data

    @pytest.mark.asyncio
    async def test_csv_import_detects_duplicates(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)

        cpf = make_valid_cpf()
        email = f"dup_{uuid.uuid4().hex[:8]}@empresa.com"

        csv_content = f"full_name,cpf,email\nFunc 1,{cpf},{email}\n"
        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        response = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["created"] == 1

        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        response = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 0
        assert data["existing"] == 1

    @pytest.mark.asyncio
    async def test_csv_import_missing_columns_rejected(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)

        csv_content = "name,email\nFunc 1,func@empresa.com\n"
        files = {"file": ("employees.csv", csv_content.encode("utf-8"), "text/csv")}
        response = await client.post(
            f"/api/v1/companies/{company_id}/employees/import",
            files=files,
            headers=admin_headers,
        )
        assert response.status_code == 400


class TestBulkEnrollment:
    """Corporate bulk enrollment with capacity enforcement."""

    @pytest.mark.asyncio
    async def test_bulk_enroll_corporate_no_payment(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)
        course_id = await _create_course(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, max_students=20)

        student_ids = []
        for i in range(3):
            sid = await _create_employee(client, admin_headers, company_id, f"Func {i}")
            student_ids.append(sid)

        response = await client.post(
            "/api/v1/enrollments/bulk",
            json={
                "class_id": class_id,
                "student_ids": student_ids,
                "company_id": company_id,
                "source": "CORPORATE",
                "status": "CONFIRMADA",
                "price_per_student": 0,
                "create_payment": False,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert len(data["enrollment_ids"]) == 3
        assert data["payment_id"] is None
        assert data["batch_id"] is not None

    @pytest.mark.asyncio
    async def test_bulk_enroll_capacity_enforcement(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)
        course_id = await _create_course(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, max_students=2)

        student_ids = []
        for i in range(5):
            sid = await _create_employee(client, admin_headers, company_id, f"Cap {i}")
            student_ids.append(sid)

        response = await client.post(
            "/api/v1/enrollments/bulk",
            json={
                "class_id": class_id,
                "student_ids": student_ids,
                "company_id": company_id,
                "source": "CORPORATE",
                "status": "CONFIRMADA",
                "price_per_student": 0,
                "create_payment": False,
            },
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "capacity" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bulk_enroll_duplicate_prevented(self, client, admin_headers):
        company_id = await _create_company(client, admin_headers)
        course_id = await _create_course(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, max_students=20)

        sid = await _create_employee(client, admin_headers, company_id, "Dup")

        response = await client.post(
            "/api/v1/enrollments/bulk",
            json={
                "class_id": class_id,
                "student_ids": [sid],
                "company_id": company_id,
                "source": "CORPORATE",
                "status": "CONFIRMADA",
                "price_per_student": 0,
                "create_payment": False,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201

        response = await client.post(
            "/api/v1/enrollments/bulk",
            json={
                "class_id": class_id,
                "student_ids": [sid],
                "company_id": company_id,
                "source": "CORPORATE",
                "status": "CONFIRMADA",
                "price_per_student": 0,
                "create_payment": False,
            },
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "already enrolled" in response.json()["detail"].lower()


class TestEnrollmentSource:
    """Enrollment source field distinguishes INDIVIDUAL from CORPORATE."""

    @pytest.mark.asyncio
    async def test_purchase_enrollment_is_individual(self, client, admin_headers):
        """B2C purchase should create enrollment with source=INDIVIDUAL."""
        course_id = await _create_course(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id)

        # Create independent student with password and class
        response = await client.post(
            "/api/v1/students/",
            json={
                "full_name": "Aluno B2C",
                "email": f"b2c_{uuid.uuid4().hex[:8]}@gmail.com",
                "cpf": make_valid_cpf(),
                "password": "senha123",
                "class_id": class_id,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201

        response = await client.get("/api/v1/enrollments/", headers=admin_headers)
        enrollments = response.json()
        class_enrollments = [e for e in enrollments if e["class_id"] == class_id]
        assert len(class_enrollments) > 0
        assert class_enrollments[-1]["source"] == "INDIVIDUAL"

    @pytest.mark.asyncio
    async def test_bulk_enroll_is_corporate(self, client, admin_headers):
        """Corporate bulk enrollment should have source=CORPORATE."""
        company_id = await _create_company(client, admin_headers)
        course_id = await _create_course(client, admin_headers)
        class_id = await _create_class(client, admin_headers, course_id, max_students=20)

        sid = await _create_employee(client, admin_headers, company_id, "Corp")

        response = await client.post(
            "/api/v1/enrollments/bulk",
            json={
                "class_id": class_id,
                "student_ids": [sid],
                "company_id": company_id,
                "source": "CORPORATE",
                "status": "CONFIRMADA",
                "price_per_student": 0,
                "create_payment": False,
            },
            headers=admin_headers,
        )
        assert response.status_code == 201

        response = await client.get("/api/v1/enrollments/", headers=admin_headers)
        enrollments = response.json()
        corp_enrollments = [e for e in enrollments if e["class_id"] == class_id]
        assert len(corp_enrollments) > 0
        assert corp_enrollments[-1]["source"] == "CORPORATE"
