"""Phase 6: Canonical progress calculation consistency test.

Verifies that the student-facing ``/courses/{course_id}/my-progress``
endpoint and the B2B ``/api/v1/b2b/...`` endpoints use the same
canonical required-only progress calculation.
"""

import uuid
from datetime import date, datetime

import httpx
import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.lesson import Lesson, LessonContentType, LessonProgress
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from tests.conftest import make_valid_cpf

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B2B_ID = "test-b2b-progress"
B2B_SECRET = "test-b2b-progress-secret-32chars!!"


async def _seed_progress_data():
    """Seed a course with 3 required + 2 optional lessons.

    Student completes:
    - 2 of 3 required lessons
    - 1 of 2 optional lessons

    Canonical progress = 2/3 * 100 = 66.7%
    (optional lesson completion does NOT count)
    """
    async with AsyncSessionLocal() as session:
        session.add(Tenant(
            id=TENANT_ID, name="Progress Tenant", slug="progress-test",
            status=TenantStatus.ACTIVE, contact_name="Test", contact_email="test@progress.com",
        ))
        await session.flush()

        # Admin + student users
        admin = User(
            tenant_id=TENANT_ID, email="admin@progress.com",
            full_name="Admin", password_hash=hash_password("pw1234567"),
            role=UserRole.ADMIN.value, is_active=True,
        )
        student_user = User(
            tenant_id=TENANT_ID, email="student@progress.com",
            full_name="Student Progress", password_hash=hash_password("pw1234567"),
            role=UserRole.STUDENT.value, is_active=True,
        )
        session.add_all([admin, student_user])
        await session.flush()

        student = Student(tenant_id=TENANT_ID, user_id=student_user.id, cpf=make_valid_cpf())
        session.add(student)
        await session.flush()

        # Course with 3 required + 2 optional lessons
        course = Course(
            tenant_id=TENANT_ID, code="PROG-TEST", name="Progress Test Course",
            category="Test", carga_horaria=8, modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO, price=100.0, is_active=True,
        )
        session.add(course)
        await session.flush()

        # 3 required lessons
        req_lessons = []
        for i in range(3):
            lesson = Lesson(
                tenant_id=TENANT_ID, course_id=course.id,
                title=f"Required Lesson {i+1}",
                content_type=LessonContentType.UPLOAD,
                video_url=f"https://example.com/req-{i+1}",
                order=i, is_required=True,
            )
            session.add(lesson)
            req_lessons.append(lesson)

        # 2 optional lessons
        opt_lessons = []
        for i in range(2):
            lesson = Lesson(
                tenant_id=TENANT_ID, course_id=course.id,
                title=f"Optional Lesson {i+1}",
                content_type=LessonContentType.UPLOAD,
                video_url=f"https://example.com/opt-{i+1}",
                order=3 + i, is_required=False,
            )
            session.add(lesson)
            opt_lessons.append(lesson)

        await session.flush()

        # Class + enrollment
        cls = Class(
            tenant_id=TENANT_ID, course_id=course.id, responsible_admin_id=admin.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(cls)
        await session.flush()

        enrollment = Enrollment(
            tenant_id=TENANT_ID, student_id=student.id, class_id=cls.id,
            status=EnrollmentStatus.CONFIRMADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 15), price=100.0,
        )
        session.add(enrollment)
        # A cancelled record must not be classified as in_progress. It uses
        # a separate class because the schema enforces one enrollment per
        # student/class pair.
        cancelled_class = Class(
            tenant_id=TENANT_ID, course_id=course.id, responsible_admin_id=admin.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(cancelled_class)
        await session.flush()
        session.add(Enrollment(
            tenant_id=TENANT_ID, student_id=student.id, class_id=cancelled_class.id,
            status=EnrollmentStatus.CANCELADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 10), price=100.0,
        ))

        # Mark 2 of 3 required lessons as completed
        for lesson in req_lessons[:2]:
            session.add(LessonProgress(
                tenant_id=TENANT_ID, student_id=student.id, lesson_id=lesson.id,
                completed=True, completed_at=datetime(2026, 1, 20),
            ))

        # Mark 1 of 2 optional lessons as completed
        session.add(LessonProgress(
            tenant_id=TENANT_ID, student_id=student.id, lesson_id=opt_lessons[0].id,
            completed=True, completed_at=datetime(2026, 1, 21),
        ))

        # B2B client
        session.add(B2BClient(
            tenant_id=TENANT_ID, client_id=B2B_ID,
            client_secret_hash=hash_password(B2B_SECRET),
            name="B2B Progress", allowed_scopes="academic:read", is_active=True,
        ))
        await session.commit()

        return {
            "course_id": course.id,
            "student_id": student.id,
            "enrollment_id": enrollment.id,
            "student_user_id": student_user.id,
        }


@pytest.fixture(autouse=True)
async def progress_seed(setup_db):
    ids = await _seed_progress_data()
    yield ids


def _b2b_headers():
    return {"X-B2B-Client-Id": B2B_ID, "X-B2B-Client-Secret": B2B_SECRET}


@pytest.mark.asyncio
async def test_canonical_progress_service(progress_seed):
    """Canonical progress service should report 66.7% (2/3 required), not 60% (3/5 all)."""
    from app.core.database import AsyncSessionLocal
    from app.services.progress_service import compute_course_progress

    async with AsyncSessionLocal() as db:
        result = await compute_course_progress(
            db, TENANT_ID, progress_seed['course_id'], progress_seed['student_id']
        )
        assert result.required_lessons == 3
        assert result.completed_required == 2
        assert result.total_lessons == 5
        assert result.completed_optional == 1
        # 2/3 * 100 = 66.67, rounded to 1 decimal place
        assert result.percentage == 66.7
        assert result.certificate_eligible is False


@pytest.mark.asyncio
async def test_b2b_enrollment_progress_uses_required_only(client: httpx.AsyncClient, progress_seed):
    """B2B enrollment detail should report 66.7% (2/3 required), not 60% (3/5 all)."""
    resp = await client.get(
        f"/api/v1/b2b/enrollments/{progress_seed['enrollment_id']}",
        headers=_b2b_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    # lessons_total should be 3 (required only), not 5 (all)
    assert data["lessons_total"] == 3
    assert data["lessons_completed"] == 2
    # 2/3 * 100 = 66.67, rounded to 1 decimal place
    assert data["progress_percent"] == 66.7


@pytest.mark.asyncio
async def test_b2b_course_progress_uses_required_only(client: httpx.AsyncClient, progress_seed):
    """B2B course progress should report avg 66.7% (2/3 required), not 60% (3/5 all)."""
    resp = await client.get(
        f"/api/v1/b2b/courses/{progress_seed['course_id']}/progress",
        headers=_b2b_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_progress_percent"] == 66.7
    assert data["total_enrollments"] == 2
    assert data["completed"] == 0
    assert data["in_progress"] == 1


@pytest.mark.asyncio
async def test_b2b_summary_avg_progress_uses_required_only(client: httpx.AsyncClient, progress_seed):
    """B2B summary avg_progress_percent should be 66.7% (required-only), not 60%."""
    resp = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_progress_percent"] == 66.7


@pytest.mark.asyncio
async def test_progress_consistency_b2b_endpoints(client: httpx.AsyncClient, progress_seed):
    """All B2B endpoints must use the same required-only progress calculation."""
    # B2B enrollment detail
    b2b_enr_resp = await client.get(
        f"/api/v1/b2b/enrollments/{progress_seed['enrollment_id']}",
        headers=_b2b_headers(),
    )
    assert b2b_enr_resp.status_code == 200
    enr_pct = b2b_enr_resp.json()["progress_percent"]

    # B2B course progress
    b2b_course_resp = await client.get(
        f"/api/v1/b2b/courses/{progress_seed['course_id']}/progress",
        headers=_b2b_headers(),
    )
    assert b2b_course_resp.status_code == 200
    course_pct = b2b_course_resp.json()["avg_progress_percent"]

    # B2B summary
    b2b_summary_resp = await client.get("/api/v1/b2b/summary", headers=_b2b_headers())
    assert b2b_summary_resp.status_code == 200
    summary_pct = b2b_summary_resp.json()["avg_progress_percent"]

    # All should be ~66.7% (required-only)
    assert abs(enr_pct - 66.7) < 0.1
    assert abs(course_pct - 66.7) < 0.1
    assert abs(summary_pct - 66.7) < 0.1
