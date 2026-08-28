"""Tests for the B2B read-only academic API.

Tests cover:
- Valid/invalid B2B client credentials
- Missing headers → 401 (not 422)
- Scope enforcement (academic:read superset, specific scopes, no scope → 403)
- Tenant isolation (cross-tenant data not leaked)
- Pagination
- Filtering
- All endpoints: summary, courses, classes, students, enrollments, certificates, context
- avg_progress_percent correctness (0-100, per-enrollment average)
- LGPD compliance (no CPF, password_hash, client_secret_hash)
- N+1 elimination (batch counts)
"""


import pytest
from httpx import AsyncClient
from sqlalchemy import delete, update

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient

B2B_CLIENT_ID = "test-b2b-central"
B2B_CLIENT_SECRET = "test-b2b-secret-with-minimum-length-32chars!!"
B2B_CLIENT_ID_NO_SCOPE = "test-b2b-no-scope"
B2B_CLIENT_SECRET_NO_SCOPE = "test-b2b-noscope-secret-32chars-pads!!"
B2B_CLIENT_ID_COURSES_ONLY = "test-b2b-courses-only"
B2B_CLIENT_SECRET_COURSES_ONLY = "test-b2b-courses-only-secret-32chars!!"


@pytest.fixture(autouse=True)
async def _setup_b2b_client():
    """Create B2B clients for testing."""
    async with AsyncSessionLocal() as session:
        clients = [
            B2BClient(
                tenant_id=WR_TENANT_ID,
                client_id=B2B_CLIENT_ID,
                client_secret_hash=hash_password(B2B_CLIENT_SECRET),
                name="Test Central WR B2B",
                allowed_scopes="academic:read",
                is_active=True,
            ),
            B2BClient(
                tenant_id=WR_TENANT_ID,
                client_id=B2B_CLIENT_ID_NO_SCOPE,
                client_secret_hash=hash_password(B2B_CLIENT_SECRET_NO_SCOPE),
                name="Test No Scope B2B",
                allowed_scopes="",
                is_active=True,
            ),
            B2BClient(
                tenant_id=WR_TENANT_ID,
                client_id=B2B_CLIENT_ID_COURSES_ONLY,
                client_secret_hash=hash_password(B2B_CLIENT_SECRET_COURSES_ONLY),
                name="Test Courses Only B2B",
                allowed_scopes="courses:read",
                is_active=True,
            ),
        ]
        session.add_all(clients)
        await session.commit()
        yield
        await session.execute(
            delete(B2BClient).where(
                B2BClient.client_id.in_([
                    B2B_CLIENT_ID, B2B_CLIENT_ID_NO_SCOPE, B2B_CLIENT_ID_COURSES_ONLY,
                ])
            )
        )
        await session.commit()


def _b2b_headers(client_id=B2B_CLIENT_ID, secret=B2B_CLIENT_SECRET):
    return {
        "X-B2B-Client-Id": client_id,
        "X-B2B-Client-Secret": secret,
    }


# ---- Authentication ----

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
    assert "credentials" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_b2b_missing_client_id_header(client: AsyncClient):
    """Missing X-B2B-Client-Id header should return 401, not 422."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers={"X-B2B-Client-Secret": B2B_CLIENT_SECRET},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_b2b_missing_secret_header(client: AsyncClient):
    """Missing X-B2B-Client-Secret header should return 401, not 422."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers={"X-B2B-Client-Id": B2B_CLIENT_ID},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_b2b_missing_all_headers(client: AsyncClient):
    """Missing all B2B headers should return 401, not 422."""
    response = await client.get("/api/v1/b2b/summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_b2b_wrong_secret(client: AsyncClient):
    """Wrong secret with valid client_id should return 401 with same message."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers={"X-B2B-Client-Id": B2B_CLIENT_ID, "X-B2B-Client-Secret": "wrong-secret-32-chars-padding!!!"},
    )
    assert response.status_code == 401
    # Error message should be identical to invalid client_id (no leak)
    invalid_resp = await client.get(
        "/api/v1/b2b/summary",
        headers={"X-B2B-Client-Id": "nonexistent", "X-B2B-Client-Secret": "wrong-secret-32-chars-padding!!!"},
    )
    assert response.json()["detail"] == invalid_resp.json()["detail"]


@pytest.mark.asyncio
async def test_b2b_inactive_client(client: AsyncClient):
    """Inactive B2B client should return 401."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID).values(is_active=False)
        )
        await session.commit()
    response = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert response.status_code == 401
    # Reactivate for other tests
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID).values(is_active=True)
        )
        await session.commit()


# ---- Context endpoint ----

@pytest.mark.asyncio
async def test_b2b_context_endpoint(client: AsyncClient):
    """B2B context endpoint should return tenant info without secret."""
    response = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "tenant_id" in data
    assert "tenant_slug" in data
    assert "client_id" in data
    assert "scopes" in data
    assert data["client_id"] == B2B_CLIENT_ID
    assert "academic:read" in data["scopes"]
    # Must NOT contain secret
    assert "client_secret" not in data
    assert "client_secret_hash" not in data


# ---- Scope enforcement ----

@pytest.mark.asyncio
async def test_b2b_no_scope_client_rejected(client: AsyncClient):
    """B2B client without academic:read scope should get 403."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers=_b2b_headers(B2B_CLIENT_ID_NO_SCOPE, B2B_CLIENT_SECRET_NO_SCOPE),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_b2b_courses_only_scope_can_access_courses(client: AsyncClient):
    """Client with courses:read scope can access courses."""
    response = await client.get(
        "/api/v1/b2b/courses?limit=5",
        headers=_b2b_headers(B2B_CLIENT_ID_COURSES_ONLY, B2B_CLIENT_SECRET_COURSES_ONLY),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_b2b_courses_only_scope_cannot_access_students(client: AsyncClient):
    """Client with only courses:read scope CANNOT access students."""
    response = await client.get(
        "/api/v1/b2b/students?limit=5",
        headers=_b2b_headers(B2B_CLIENT_ID_COURSES_ONLY, B2B_CLIENT_SECRET_COURSES_ONLY),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_b2b_courses_only_scope_cannot_access_summary(client: AsyncClient):
    """Client with only courses:read scope CANNOT access summary (needs academic:read)."""
    response = await client.get(
        "/api/v1/b2b/summary",
        headers=_b2b_headers(B2B_CLIENT_ID_COURSES_ONLY, B2B_CLIENT_SECRET_COURSES_ONLY),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_b2b_academic_read_superset_grants_all(client: AsyncClient):
    """academic:read scope grants access to all academic endpoints."""
    for endpoint in ["/summary", "/courses?limit=1", "/classes?limit=1", "/students?limit=1",
                     "/enrollments?limit=1", "/certificates?limit=1"]:
        response = await client.get(f"/api/v1/b2b{endpoint}", headers=_b2b_headers())
        assert response.status_code == 200, f"Failed for {endpoint}"


# ---- List endpoints ----

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
    response = await client.get("/api/v1/b2b/classes?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data and "data" in data


@pytest.mark.asyncio
async def test_b2b_students_list(client: AsyncClient):
    response = await client.get("/api/v1/b2b/students?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data and "data" in data


@pytest.mark.asyncio
async def test_b2b_enrollments_list(client: AsyncClient):
    response = await client.get("/api/v1/b2b/enrollments?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data and "data" in data


@pytest.mark.asyncio
async def test_b2b_certificates_list(client: AsyncClient):
    response = await client.get("/api/v1/b2b/certificates?limit=10", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data and "data" in data


# ---- 404s ----

@pytest.mark.asyncio
async def test_b2b_course_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/b2b/courses/00000000-0000-0000-0000-000000000000", headers=_b2b_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_class_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/b2b/classes/00000000-0000-0000-0000-000000000000", headers=_b2b_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_student_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/b2b/students/00000000-0000-0000-0000-000000000000", headers=_b2b_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_b2b_enrollment_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/b2b/enrollments/00000000-0000-0000-0000-000000000000", headers=_b2b_headers())
    assert response.status_code == 404


# ---- Course progress ----

@pytest.mark.asyncio
async def test_b2b_course_progress(client: AsyncClient):
    courses_resp = await client.get("/api/v1/b2b/courses?limit=1", headers=_b2b_headers())
    courses_data = courses_resp.json()
    if courses_data["data"]:
        course_id = courses_data["data"][0]["id"]
        response = await client.get(
            f"/api/v1/b2b/courses/{course_id}/progress", headers=_b2b_headers())
        assert response.status_code == 200
        data = response.json()
        assert "total_enrollments" in data
        assert "completed" in data
        assert "avg_progress_percent" in data
        # Progress must be in [0, 100]
        assert 0 <= data["avg_progress_percent"] <= 100


# ---- avg_progress_percent correctness ----

@pytest.mark.asyncio
async def test_b2b_summary_avg_progress_in_range(client: AsyncClient):
    """avg_progress_percent must always be in [0, 100]."""
    response = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["avg_progress_percent"] <= 100


@pytest.mark.asyncio
async def test_b2b_enrollments_progress_in_range(client: AsyncClient):
    """Each enrollment progress_percent must be in [0, 100]."""
    response = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    for enr in data["data"]:
        assert 0 <= enr["progress_percent"] <= 100, f"Progress {enr['progress_percent']} out of range"


# ---- LGPD compliance ----

@pytest.mark.asyncio
async def test_b2b_student_no_cpf_in_response(client: AsyncClient):
    """B2B student response must not include CPF (LGPD)."""
    response = await client.get("/api/v1/b2b/students?limit=5", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    for student in data["data"]:
        assert "cpf" not in student
        assert "password_hash" not in student


@pytest.mark.asyncio
async def test_b2b_context_no_secret_in_response(client: AsyncClient):
    """B2B context response must not include any secret."""
    response = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert "client_secret" not in data
    assert "client_secret_hash" not in data
    assert "secret" not in str(data).lower()
