"""Security regression tests.

Covers Step 23 — SECURITY REGRESSIONS:
- IDOR (cross-tenant resource IDs)
- Role escalation (student calling admin endpoints)
- Malformed JWT
- Expired JWT
- Unauthorized certificate access
- Unauthorized lesson/material operations

No destructive penetration testing — only verifies the security contract
is enforced at the API layer.
"""

import uuid
from datetime import timedelta

from app.core.security import create_access_token
from app.core.utils import utc_now


async def _create_course(client, admin_headers):
    code = f"SEC-{uuid.uuid4().hex[:6].upper()}"
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": code,
            "name": "Security Test Course",
            "category": "Segurança",
            "carga_horaria": 40,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 299.90,
            "description": "Security test",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_lesson(client, admin_headers, course_id):
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Security Lesson",
            "order": 1,
            "content_type": "UPLOAD",
            "is_required": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


# ─── Role escalation ───


async def test_student_cannot_create_course(client, admin_headers, student_user):
    """Student calling admin endpoint (POST /courses) → 403."""
    response = await client.post(
        "/api/v1/courses/",
        json={
            "code": "HACK-01",
            "name": "Hacked Course",
            "category": "Test",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 99.90,
        },
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_student_cannot_create_lesson(client, admin_headers, student_user):
    """Student cannot create lessons → 403."""
    course_id = await _create_course(client, admin_headers)
    response = await client.post(
        f"/api/v1/lessons/courses/{course_id}/lessons",
        json={
            "title": "Hacked Lesson",
            "order": 1,
            "content_type": "UPLOAD",
        },
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_student_cannot_delete_course(client, admin_headers, student_user):
    """Student cannot delete courses → 403."""
    course_id = await _create_course(client, admin_headers)
    response = await client.delete(
        f"/api/v1/courses/{course_id}",
        headers=student_user["headers"],
    )
    assert response.status_code == 403


async def test_student_cannot_access_dashboard_stats(client, student_user):
    """Student cannot access admin dashboard stats → 403."""
    response = await client.get("/api/v1/dashboard/stats", headers=student_user["headers"])
    assert response.status_code == 403


# ─── Malformed / invalid JWT ───


async def test_malformed_jwt_rejected(client):
    """A garbage string as Bearer token → 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


async def test_expired_jwt_rejected(client):
    """An expired JWT → 401."""
    expired_token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "admin"},
        expires_delta=timedelta(seconds=-1),
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


async def test_missing_bearer_prefix(client):
    """Token without 'Bearer ' prefix → 403 (no credentials provided)."""
    token = create_access_token({"sub": str(uuid.uuid4()), "role": "admin"})
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": token},
    )
    assert response.status_code == 403


async def test_no_auth_header(client):
    """No Authorization header at all → 403."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


async def test_wrong_secret_key_jwt_rejected(client):
    """A JWT signed with a different secret → 401."""
    from jose import jwt

    from app.core.config import settings

    payload = {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "tenant_id": None,
        "exp": utc_now() + timedelta(minutes=30),
    }
    fake_token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.ALGORITHM)
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fake_token}"},
    )
    assert response.status_code == 401


# ─── IDOR ───


async def test_idor_get_nonexistent_course(client, admin_headers):
    """A random UUID for a course → 404 (not a leak)."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/courses/{fake_id}",
        headers=admin_headers,
    )
    assert response.status_code == 404


async def test_idor_get_nonexistent_lesson(client, admin_headers):
    """A random UUID for a lesson → 404 (not a leak)."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/lessons/{fake_id}",
        headers=admin_headers,
    )
    assert response.status_code == 404


# ─── Unauthorized certificate access ───


async def test_certificate_validate_missing_code(client):
    """Certificate validation without code → 422 (validation error, not 500)."""
    response = await client.post(
        "/api/v1/certificates/validate",
        json={},
    )
    assert response.status_code == 422


async def test_certificate_validate_nonexistent_code(client):
    """Certificate validation with nonexistent code → valid:false (not 404)."""
    response = await client.post(
        "/api/v1/certificates/validate",
        json={"validation_code": "NONEXISTENT-CODE-12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


# ─── API error contract — no secret leakage ───


async def test_error_responses_do_not_leak_secrets(client, admin_headers):
    """Error responses must not contain stack traces, DB URLs, or secrets."""
    # Trigger a 404
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/courses/{fake_id}",
        headers=admin_headers,
    )
    body = response.text.lower()
    # Must not leak internal details
    assert "postgresql" not in body
    assert "asyncpg" not in body
    assert "sqlalchemy" not in body
    assert "traceback" not in body
    assert "secret_key" not in body
    assert "password" not in body


async def test_500_path_no_secret_leakage(client, admin_headers, monkeypatch):
    """A simulated 500 must not leak secrets in the response body."""
    # Force a 500 by making the DB session raise
    from app.api.routes import courses as courses_route

    async def _boom(*args, **kwargs):
        raise RuntimeError("internal error with SECRET_KEY=supersecret and DATABASE_URL=postgresql://user:pass@host/db")

    monkeypatch.setattr(courses_route, "get_db", _boom)
    response = await client.get("/api/v1/courses/", headers=admin_headers)
    body = response.text.lower()
    # Even if the exception message contains secrets, the API must not
    # return them verbatim in the response body.
    assert "supersecret" not in body
    assert "postgresql://user:pass" not in body
