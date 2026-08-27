"""Tests for CourseContentProfile and CourseMaterial models and routes."""
import uuid

import pytest
from fastapi import status


async def _admin_id(client, admin_headers):
    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    return me.json()["id"]


async def _create_course(client, admin_headers, code=None):
    payload = {
        "code": code or f"TEST-{uuid.uuid4().hex[:6].upper()}",
        "name": "Curso Teste Content",
        "category": "Segurança",
        "carga_horaria": 40,
        "modality": "PRESENCIAL",
        "price": 100.0,
        "description": "Curso teste para content profile",
    }
    response = await client.post("/api/v1/courses/", json=payload, headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


class TestCourseContentProfile:
    @pytest.mark.asyncio
    async def test_create_and_get(self, client, admin_headers):
        """Admin can create a content profile; anyone can read it."""
        course_id = await _create_course(client, admin_headers)

        resp = await client.post(
            f"/api/v1/courses/{course_id}/content-profile",
            json={
                "course_id": course_id,
                "short_description": "Treinamento sobre NR 10",
                "full_description": "Curso completo sobre segurança em eletricidade",
                "target_audience": "Eletricistas",
                "general_objective": "Capacitar trabalhadores",
                "specific_objectives": ["Identificar riscos", "Aplicar EPIs"],
                "syllabus": ["Módulo 1", "Módulo 2"],
                "key_topics": ["Riscos elétricos", "EPIs"],
                "standards_referenced": ["NR 10"],
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        profile = resp.json()
        assert profile["short_description"] == "Treinamento sobre NR 10"
        assert profile["specific_objectives"] == ["Identificar riscos", "Aplicar EPIs"]

        # Read (public — no auth needed)
        resp2 = await client.get(f"/api/v1/courses/{course_id}/content-profile")
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["short_description"] == "Treinamento sobre NR 10"

    @pytest.mark.asyncio
    async def test_update(self, client, admin_headers):
        """Admin can update a content profile."""
        course_id = await _create_course(client, admin_headers)

        await client.post(
            f"/api/v1/courses/{course_id}/content-profile",
            json={"course_id": course_id, "short_description": "Original"},
            headers=admin_headers,
        )

        resp = await client.put(
            f"/api/v1/courses/{course_id}/content-profile",
            json={"short_description": "Updated description", "target_audience": "New audience"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["short_description"] == "Updated description"
        assert resp.json()["target_audience"] == "New audience"

    @pytest.mark.asyncio
    async def test_duplicate_rejected(self, client, admin_headers):
        """Creating a duplicate profile for the same course returns 409."""
        course_id = await _create_course(client, admin_headers)

        await client.post(
            f"/api/v1/courses/{course_id}/content-profile",
            json={"course_id": course_id, "short_description": "First"},
            headers=admin_headers,
        )

        resp = await client.post(
            f"/api/v1/courses/{course_id}/content-profile",
            json={"course_id": course_id, "short_description": "Second"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_not_found(self, client, admin_headers):
        """Getting a profile that doesn't exist returns 404."""
        course_id = await _create_course(client, admin_headers)
        resp = await client.get(f"/api/v1/courses/{course_id}/content-profile")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_student_cannot_create(self, client, admin_headers, student_user):
        """Non-admin users cannot create content profiles."""
        course_id = await _create_course(client, admin_headers)

        resp = await client.post(
            f"/api/v1/courses/{course_id}/content-profile",
            json={"course_id": course_id, "short_description": "Test"},
            headers=student_user["headers"],
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestCourseMaterial:
    @pytest.mark.asyncio
    async def test_create_and_list(self, client, admin_headers, student_user):
        """Admin can create materials; enrolled students can list."""
        from datetime import timedelta

        from app.core.utils import utc_now

        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)

        # Create class and enroll student
        today = utc_now().date()
        class_resp = await client.post(
            "/api/v1/classes/",
            json={
                "course_id": course_id,
                "responsible_admin_id": admin_id,
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
                "max_students": 20,
                "location": "Sala Teste",
                "ead_link": None,
            },
            headers=admin_headers,
        )
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        enr_resp = await client.post(
            "/api/v1/enrollments/",
            json={"student_id": student_user["student_id"], "class_id": class_id, "price": 100.0},
            headers=admin_headers,
        )
        assert enr_resp.status_code == 201
        enrollment_id = enr_resp.json()["id"]

        # Confirm enrollment
        await client.put(
            f"/api/v1/enrollments/{enrollment_id}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )

        # Create material
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials",
            json={
                "course_id": course_id,
                "title": "Apostila NR 10",
                "storage_key": f"test/courses/{course_id}/nr10.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024000,
                "sha256": f"hash_{uuid.uuid4().hex[:8]}",
                "document_type": "APOSTILA",
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["title"] == "Apostila NR 10"

        # List as enrolled student
        resp2 = await client.get(
            f"/api/v1/courses/{course_id}/materials",
            headers=student_user["headers"],
        )
        assert resp2.status_code == status.HTTP_200_OK
        assert len(resp2.json()) == 1
        assert resp2.json()[0]["title"] == "Apostila NR 10"

    @pytest.mark.asyncio
    async def test_duplicate_sha256_rejected(self, client, admin_headers):
        """Duplicate SHA-256 for the same course returns 409."""
        course_id = await _create_course(client, admin_headers)
        sha = "same_hash_abc123"

        payload = {
            "course_id": course_id,
            "title": "Apostila 1",
            "storage_key": "test/key1.pdf",
            "sha256": sha,
        }

        resp1 = await client.post(f"/api/v1/courses/{course_id}/materials", json=payload, headers=admin_headers)
        assert resp1.status_code == status.HTTP_201_CREATED

        payload["title"] = "Apostila 2"
        payload["storage_key"] = "test/key2.pdf"
        resp2 = await client.post(f"/api/v1/courses/{course_id}/materials", json=payload, headers=admin_headers)
        assert resp2.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_unenrolled_student_forbidden(self, client, admin_headers, student_user):
        """Unenrolled students cannot list materials."""
        course_id = await _create_course(client, admin_headers)

        await client.post(
            f"/api/v1/courses/{course_id}/materials",
            json={"course_id": course_id, "title": "Test", "storage_key": "test/key.pdf", "sha256": "hash_xyz"},
            headers=admin_headers,
        )

        resp = await client.get(f"/api/v1/courses/{course_id}/materials", headers=student_user["headers"])
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_deactivate(self, client, admin_headers, student_user):
        """Deleting a material deactivates it (soft delete)."""
        from datetime import timedelta

        from app.core.utils import utc_now

        course_id = await _create_course(client, admin_headers)
        admin_id = await _admin_id(client, admin_headers)

        # Enroll student
        today = utc_now().date()
        class_resp = await client.post(
            "/api/v1/classes/",
            json={
                "course_id": course_id,
                "responsible_admin_id": admin_id,
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
                "max_students": 20,
                "location": "Sala Teste",
                "ead_link": None,
            },
            headers=admin_headers,
        )
        class_id = class_resp.json()["id"]

        enr_resp = await client.post(
            "/api/v1/enrollments/",
            json={"student_id": student_user["student_id"], "class_id": class_id, "price": 100.0},
            headers=admin_headers,
        )
        await client.put(
            f"/api/v1/enrollments/{enr_resp.json()['id']}",
            json={"status": "CONFIRMADA"},
            headers=admin_headers,
        )

        # Create material
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials",
            json={"course_id": course_id, "title": "To Delete", "storage_key": "test/del.pdf", "sha256": "del_hash_001"},
            headers=admin_headers,
        )
        material_id = resp.json()["id"]

        # Delete (deactivate)
        resp2 = await client.delete(
            f"/api/v1/courses/{course_id}/materials/{material_id}",
            headers=admin_headers,
        )
        assert resp2.status_code == status.HTTP_204_NO_CONTENT

        # List should be empty (only active materials)
        resp3 = await client.get(f"/api/v1/courses/{course_id}/materials", headers=student_user["headers"])
        assert resp3.status_code == status.HTTP_200_OK
        assert len(resp3.json()) == 0

    @pytest.mark.asyncio
    async def test_update(self, client, admin_headers):
        """Admin can update material metadata."""
        course_id = await _create_course(client, admin_headers)

        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials",
            json={"course_id": course_id, "title": "Original Title", "storage_key": "test/key.pdf", "sha256": "upd_hash_001"},
            headers=admin_headers,
        )
        material_id = resp.json()["id"]

        resp2 = await client.put(
            f"/api/v1/courses/{course_id}/materials/{material_id}",
            json={"title": "Updated Title", "is_active": False},
            headers=admin_headers,
        )
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["title"] == "Updated Title"
        assert resp2.json()["is_active"] is False


class TestCourseMaterialUploadFlow:
    """Tests for the presigned upload + complete flow."""

    @pytest.mark.asyncio
    async def test_upload_url_admin_only(self, client, student_user):
        """Non-admin cannot request upload URL."""
        course_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "a1b2c3d4" * 8,
            },
            headers=student_user["headers"],
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_upload_url_invalid_mime(self, client, admin_headers):
        """Invalid mime type is rejected."""
        course_id = await _create_course(client, admin_headers)
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "test.exe",
                "mime_type": "application/x-msdownload",
                "size_bytes": 1024,
                "sha256": "b1a2c3d4" * 8,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    @pytest.mark.asyncio
    async def test_upload_url_size_too_large(self, client, admin_headers):
        """Oversized file is rejected."""
        course_id = await _create_course(client, admin_headers)
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "huge.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 200 * 1024 * 1024,  # 200 MB > 100 MB limit
                "sha256": "c1d2e3f4" * 8,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_upload_url_course_not_found(self, client, admin_headers):
        """Non-existent course returns 404."""
        resp = await client.post(
            f"/api/v1/courses/{uuid.uuid4()}/materials/upload-url",
            json={
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "d1c2b3a4" * 8,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_upload_url_invalid_sha(self, client, admin_headers):
        """Malformed SHA-256 is rejected."""
        course_id = await _create_course(client, admin_headers)
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "not-a-valid-sha",
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_upload_url_duplicate_sha(self, client, admin_headers):
        """Duplicate SHA returns 409."""
        course_id = await _create_course(client, admin_headers)
        sha = "e1f2d3c4" * 8

        # Create first material with this SHA
        await client.post(
            f"/api/v1/courses/{course_id}/materials",
            json={
                "course_id": course_id,
                "title": "First",
                "storage_key": "test/key1.pdf",
                "sha256": sha,
            },
            headers=admin_headers,
        )

        # Request upload URL with same SHA
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "second.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": sha,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_complete_wrong_tenant_key(self, client, admin_headers):
        """Storage key with wrong tenant prefix is rejected."""
        course_id = await _create_course(client, admin_headers)
        wrong_key = f"tenants/{uuid.uuid4()}/courses/{uuid.uuid4()}/materials/abc/test.pdf"
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/complete",
            json={
                "storage_key": wrong_key,
                "title": "Test",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "f1e2d3c4" * 8,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_complete_object_not_found(self, client, admin_headers, monkeypatch):
        """Complete fails if object doesn't exist in storage (local mode)."""
        monkeypatch.setattr("app.core.storage._is_local_backend", lambda: True)

        course_id = await _create_course(client, admin_headers)
        # In local mode, the object won't exist since we didn't upload it
        # Use a valid tenant/course prefix
        tenant_id = "11111111-1111-1111-1111-111111111111"
        valid_key = f"tenants/{tenant_id}/courses/{course_id}/materials/abc123/test.pdf"
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/complete",
            json={
                "storage_key": valid_key,
                "title": "Test",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
            },
            headers=admin_headers,
        )
        # In local mode, object won't exist → 422
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_complete_admin_only(self, client, student_user):
        """Non-admin cannot complete upload."""
        course_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/complete",
            json={
                "storage_key": "tenants/11111111-1111-1111-1111-111111111111/courses/x/materials/abc/test.pdf",
                "title": "Test",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "sha256": "01234567" * 8,
            },
            headers=student_user["headers"],
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_upload_url_local_mode_success(self, client, admin_headers, monkeypatch):
        """In local mode, upload URL endpoint returns a backend URL."""
        monkeypatch.setattr("app.core.storage._is_local_backend", lambda: True)

        course_id = await _create_course(client, admin_headers)
        sha = "a1b2c3d4" * 8
        resp = await client.post(
            f"/api/v1/courses/{course_id}/materials/upload-url",
            json={
                "filename": "apostila.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 50000,
                "sha256": sha,
            },
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK, f"Body: {resp.text}"
        data = resp.json()
        assert "upload_url" in data
        assert "storage_key" in data
        assert "expires_in" in data
        # Storage key should contain the tenant/course prefix
        assert "materials/" in data["storage_key"]
