import uuid


class TestRouteErrors:
    async def test_auth_me_user_not_found(self, client, admin_headers):
        """Força 404 no /me removendo o usuário do token."""

        from app.core.database import AsyncSessionLocal
        from app.models.user import User

        # busca e remove o admin do token
        me = await client.get("/api/v1/auth/me", headers=admin_headers)
        user_id = me.json()["id"]
        async with AsyncSessionLocal() as session:
            user = await session.get(User, uuid.UUID(user_id))
            await session.delete(user)
            await session.commit()

        response = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert response.status_code == 404

    async def test_login_invalid_identifier(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "notvalid", "password": "x"},
        )
        assert response.status_code == 400

    async def test_course_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/courses/{fake}", headers=admin_headers)).status_code == 404
        assert (await client.put(f"/api/v1/courses/{fake}", json={"name": "x"}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/courses/{fake}", headers=admin_headers)).status_code == 404

    async def test_class_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/classes/{fake}")).status_code == 404
        assert (await client.put(f"/api/v1/classes/{fake}", json={"max_students": 1}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/classes/{fake}", headers=admin_headers)).status_code == 404

    async def test_company_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/companies/{fake}", headers=admin_headers)).status_code == 404
        assert (await client.put(f"/api/v1/companies/{fake}", json={"legal_name": "x"}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/companies/{fake}", headers=admin_headers)).status_code == 404

    async def test_student_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/students/{fake}", headers=admin_headers)).status_code == 404
        assert (await client.put(f"/api/v1/students/{fake}", json={"city": "x"}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/students/{fake}", headers=admin_headers)).status_code == 404

    async def test_enrollment_not_found(self, client, admin_headers, student_user):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/enrollments/{fake}", headers=student_user["headers"])).status_code == 404
        assert (await client.put(f"/api/v1/enrollments/{fake}", json={"status": "CONFIRMADA"}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/enrollments/{fake}", headers=admin_headers)).status_code == 404

    async def test_payment_not_found(self, client, admin_headers, student_user):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/payments/{fake}", headers=student_user["headers"])).status_code == 404
        assert (await client.put(f"/api/v1/payments/{fake}", json={"status": "APROVADO"}, headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/payments/{fake}", headers=admin_headers)).status_code == 404

    async def test_certificate_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        assert (await client.get(f"/api/v1/certificates/{fake}", headers=admin_headers)).status_code == 404
        assert (await client.delete(f"/api/v1/certificates/{fake}", headers=admin_headers)).status_code == 404

    async def test_lesson_upload_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/lessons/{fake}/upload-url",
            params={"filename": "x.mp4", "content_type": "video/mp4"},
            headers=admin_headers,
        )
        assert response.status_code == 404

    async def test_lesson_watch_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        response = await client.get(f"/api/v1/lessons/{fake}/watch-url", headers=admin_headers)
        assert response.status_code == 404

    async def test_lesson_progress_not_found(self, client, student_user):
        fake = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/lessons/{fake}/progress",
            json={"watched_seconds": 10, "completed": False},
            headers=student_user["headers"],
        )
        assert response.status_code == 404

    async def test_lesson_materials_not_found(self, client, admin_headers):
        fake = str(uuid.uuid4())
        response = await client.get(f"/api/v1/lessons/{fake}/materials", headers=admin_headers)
        assert response.status_code == 404
