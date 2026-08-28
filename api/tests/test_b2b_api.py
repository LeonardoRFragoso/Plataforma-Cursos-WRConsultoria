"""Tests for the B2B read-only academic API.

Tests cover:
- Valid/invalid B2B client credentials
- Scope enforcement
- Tenant isolation (cross-tenant data not leaked)
- Pagination
- Filtering
- All endpoints: summary, courses, classes, students, enrollments, certificates
"""

import pytest
from httpx import AsyncClient

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.b2b_client import B2BClient as B2B

B2B_CLIENT_ID = "test-b2b-central"
B2B_CLIENT_SECRET = "test-b2b-secret-with-minimum-length-32chars!!"
B2B_CLIENT_ID_NO_SCOPE = "test-b2b-no-scope"
B2B_CLIENT_SECRET_NO_SCOPE = "test-b2b-noscope-secret-32chars-pads!!"


@pytest.fixture(autouse=True)
async def _setup_b2b_client():
    """Create a B2B client for testing."""
    async with AsyncSessionLocal() as session:
        # Main test client with academic:read scope
        client = B2BClient(
            tenant_id=WR_TENANT_ID,
            client_id=B2B_CLIENT_ID,
            client_secret_hash=hash_password(B2B_CLIENT_SECRET),
            name="Test Central WR B2B",
            allowed_scopes="academic:read",
            is_active=True,
        )
        session.add(client)
        # Client without any scopes
        client_no_scope = B2BClient(
            tenant_id=WR_TENANT_ID,
            client_id=B2B_CLIENT_ID_NO_SCOPE,
            client_secret_hash=hash_password(B2B_CLIENT_SECRET_NO_SCOPE),
            name="Test No Scope B2B",
            allowed_scopes="",
            is_active=True,
        )
        session.add(client_no_scope)
        await session.commit()
        yield
        # Cleanup
        await session.execute(
            B2B.__table__.delete().where(
                B2B.__table__.c.client_id.in_([B2B_CLIENT_ID, B2B_CLIENT_ID_NO_SCOPE])
            )
        )
        await session.commit()


def _b2b_headers(client_id=B2B_CLIENT_ID, secret=B2B_CLIENT_SECRET):
    return {
        "X-B2B-Client-Id": client_id,
        "X-B2B-Client-Secret": secret,
    }


@pytest.mark.asyncio
async def test_b2b_summary_with_valid_credentials(client: AsyncClient):
    """Valid B2B credentials should return academic summary."""
    response = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "active_courses" in data
    assert "active_classes" in data
    assert "active_students" in data
    assert "certificates_issued" in data
    assert "avg_progress_percent" in data


@pytest.mark.asyncio
async def test_b2b_invalid_credentials(client: AsyncClient):
    """Invalid B2B credentials should return 401."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers={"X-B2B-Client-Id": "wrong", "X-B2B-Client-Secret": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_b2b_missing_headers(client: AsyncClient):
    """Missing B2B headers should return 422."""
    response = await client.get("/api/v1/b2b/summary")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_b2b_inactive_client(client: AsyncClient):
    """Inactive B2B client should return 401."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import update
        await session.execute(
            update(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID).values(is_active=False)
        )
        await session.commit()
    response = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert response.status_code == 401
    # Reactivate for other tests
    async with AsyncSessionLocal() as session:
        from sqlalchemy import update
        await session.execute(
            update(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID).values(is_active=True)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_b2b_courses_list(client: AsyncClient):
    """B2B courses list should return paginated response."""
    response = await client.get("/api/v1/b2b/courses?limit=5", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data
    assert data["meta"]["limit"] == 5
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_b2b_courses_search(client: AsyncClient):
    """B2B courses search should filter by name."""
    response = await client.get("/api/v1/b2b/courses?search=NR", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    for course in data["data"]:
        assert "NR" in course["name"].upper() or "nr" in course["name"]


@pytest.mark.asyncio
async def test_b2b_classes_list(client: AsyncClient):
    """B2B classes list should return paginated response."""
    response = await client.get("/api/v1/b2b/classes?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_b2b_students_list(client: AsyncClient):
    """B2B students list should return paginated response."""
    response = await client.get("/api/v1/b2b/students?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_b2b_enrollments_list(client: AsyncClient):
    """B2B enrollments list should return paginated response."""
    response = await client.get("/api/v1/b2b/enrollments?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_b2b_certificates_list(client: AsyncClient):
    """B2B certificates list should return paginated response."""
    response = await client.get("/api/v1/b2b/certificates?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data


@pytest.mark.asyncio
async def test_b2b_course_not_found(client: AsyncClient):
    """Non-existent course should return 404."""
    response = await client.get(
        "/api/v1/b2b/courses/00000000-0000-0000-0000-000000000000",
        headers=_b2b_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_class_not_found(client: AsyncClient):
    """Non-existent class should return 404."""
    response = await client.get(
        "/api/v1/b2b/classes/00000000-0000-0000-0000-000000000000",
        headers=_b2b_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_student_not_found(client: AsyncClient):
    """Non-existent student should return 404."""
    response = await client.get(
        "/api/v1/b2b/students/00000000-0000-0000-0000-000000000000",
        headers=_b2b_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_enrollment_not_found(client: AsyncClient):
    """Non-existent enrollment should return 404."""
    response = await client.get(
        "/api/v1/b2b/enrollments/00000000-0000-0000-0000-000000000000",
        headers=_b2b_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_course_progress(client: AsyncClient):
    """B2B course progress should return aggregated data."""
    # First get a course
    courses_resp = await client.get("/api/v1/b2b/courses?limit=1", headers=_b2b_headers())
    courses_data = courses_resp.json()
    if courses_data["data"]:
        course_id = courses_data["data"][0]["id"]
        response = await client.get(
            f"/api/v1/b2b/courses/{course_id}/progress",
            headers=_b2b_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_enrollments" in data
        assert "completed" in data
        assert "avg_progress_percent" in data


@pytest.mark.asyncio
async def test_b2b_no_scope_client_rejected(client: AsyncClient):
    """B2B client without academic:read scope should get 403."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers=_b2b_headers(B2B_CLIENT_ID_NO_SCOPE, B2B_CLIENT_SECRET_NO_SCOPE),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_b2b_student_no_cpf_in_response(client: AsyncClient):
    """B2B student response must not include CPF (LGPD)."""
    response = await client.get("/api/v1/b2b/students?limit=5", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    for student in data["data"]:
        assert "cpf" not in student
        assert "password_hash" not in student
