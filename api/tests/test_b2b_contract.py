"""Contract tests for LMS B2B API — validates response schemas match
what Central-WR expects to consume.

These tests run against the actual LMS B2B endpoints with test credentials
and validate that the response structure matches the documented contract
(version 1). If the LMS changes a field name, type, or removes a field,
these tests will fail before Central-WR breaks in production.

Contract version: 1
See: docs/contracts/lms-integration-v1.md
"""

import pytest
from httpx import AsyncClient

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient

B2B_CLIENT_ID = "contract-test-central"
B2B_CLIENT_SECRET = "contract-test-secret-32chars-minimum!!"


@pytest.fixture(autouse=True)
async def _setup_b2b_contract_client():
    """Create a B2B client for contract testing."""
    async with AsyncSessionLocal() as session:
        client = B2BClient(
            tenant_id=WR_TENANT_ID,
            client_id=B2B_CLIENT_ID,
            client_secret_hash=hash_password(B2B_CLIENT_SECRET),
            name="Contract Test Central WR",
            allowed_scopes="academic:read",
            is_active=True,
        )
        session.add(client)
        await session.commit()
        yield
        from sqlalchemy import delete
        await session.execute(
            delete(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID)
        )
        await session.commit()


def _b2b_headers():
    return {
        "X-B2B-Client-Id": B2B_CLIENT_ID,
        "X-B2B-Client-Secret": B2B_CLIENT_SECRET,
    }


# ─── Contract: B2B Context ──────────────────────────────────────────────────

class TestB2BContextContract:
    """GET /api/v1/b2b/context must return the contract schema."""

    async def test_context_response_fields(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        # Required fields that Central-WR expects
        assert "tenant_id" in data
        assert "tenant_slug" in data
        assert "client_id" in data
        assert "scopes" in data
        # Additive field (may or may not be present, but if present must be str)
        if "api_version" in data:
            assert isinstance(data["api_version"], str)

    async def test_context_tenant_id_is_uuid_string(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
        data = resp.json()
        # Central-WR parses this as UUID
        assert data["tenant_id"] is not None
        assert len(data["tenant_id"]) == 36  # UUID string length

    async def test_context_scopes_is_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
        data = resp.json()
        assert isinstance(data["scopes"], list)
        assert "academic:read" in data["scopes"]


# ─── Contract: B2B Summary ──────────────────────────────────────────────────

class TestB2BSummaryContract:
    """GET /api/v1/b2b/summary must return all 8 KPI fields."""

    REQUIRED_FIELDS = [
        "active_courses", "active_classes", "active_students",
        "active_enrollments", "completed_enrollments", "certificates_issued",
        "avg_progress_percent", "classes_in_progress",
    ]

    async def test_summary_all_fields_present(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        for field in self.REQUIRED_FIELDS:
            assert field in data, f"Missing required field: {field}"

    async def test_summary_int_fields_are_int(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
        data = resp.json()
        int_fields = [f for f in self.REQUIRED_FIELDS if f != "avg_progress_percent"]
        for field in int_fields:
            assert isinstance(data[field], int), f"{field} should be int, got {type(data[field])}"

    async def test_summary_avg_progress_is_float(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
        data = resp.json()
        assert isinstance(data["avg_progress_percent"], (int, float))


# ─── Contract: B2B Courses ──────────────────────────────────────────────────

class TestB2BCoursesContract:
    """GET /api/v1/b2b/courses must return paginated response."""

    async def test_courses_response_structure(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/courses", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "skip" in data["meta"]
        assert "limit" in data["meta"]
        assert "total" in data["meta"]


# ─── Contract: B2B Classes ──────────────────────────────────────────────────

class TestB2BClassesContract:
    """GET /api/v1/b2b/classes must return paginated response."""

    async def test_classes_response_structure(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/classes", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "data" in data
        assert isinstance(data["data"], list)


# ─── Contract: B2B Students ─────────────────────────────────────────────────

class TestB2BStudentsContract:
    """GET /api/v1/b2b/students must return paginated response."""

    async def test_students_response_structure(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/students", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "data" in data
        assert isinstance(data["data"], list)


# ─── Contract: B2B Enrollments ──────────────────────────────────────────────

class TestB2BEnrollmentsContract:
    """GET /api/v1/b2b/enrollments must return paginated response."""

    async def test_enrollments_response_structure(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/enrollments", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "data" in data
        assert isinstance(data["data"], list)


# ─── Contract: B2B Certificates ─────────────────────────────────────────────

class TestB2BCertificatesContract:
    """GET /api/v1/b2b/certificates must return paginated response."""

    async def test_certificates_response_structure(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/certificates", headers=_b2b_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "data" in data
        assert isinstance(data["data"], list)


# ─── Contract: Error responses ──────────────────────────────────────────────

class TestB2BErrorContract:
    """B2B endpoints must return consistent error responses."""

    async def test_missing_headers_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/b2b/context")
        assert resp.status_code == 401

    async def test_invalid_credentials_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/b2b/context",
            headers={"X-B2B-Client-Id": "invalid", "X-B2B-Client-Secret": "invalid"},
        )
        assert resp.status_code == 401

    async def test_not_found_returns_404(self, client: AsyncClient):
        import uuid
        resp = await client.get(
            f"/api/v1/b2b/courses/{uuid.uuid4()}",
            headers=_b2b_headers(),
        )
        assert resp.status_code == 404


# ─── Contract: SSO Exchange ─────────────────────────────────────────────────

class TestSsoExchangeContract:
    """POST /api/v1/sso/exchange must accept the contract request schema."""

    async def test_sso_exchange_rejects_invalid_code(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/sso/exchange",
            json={
                "code": "invalid-code",
                "state": "invalid-state",
                "target_application": "lms-wr-cursos",
            },
        )
        # Should return 400 or 502 (Central rejects the code)
        assert resp.status_code in (400, 502, 503)

    async def test_sso_exchange_requires_code_and_state(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/sso/exchange",
            json={"target_application": "lms-wr-cursos"},
        )
        assert resp.status_code == 422  # Validation error
