"""B2B read-only academic API for Central WR integration.

All endpoints require B2B client credentials (X-B2B-Client-Id +
X-B2B-Client-Secret) and the ``academic:read`` scope. Data is
tenant-scoped to the B2B client's registered tenant.

These endpoints are aggregated and read-only — Central WR never
writes academic data through this API.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.b2b_security import B2BClient, require_b2b_scope
from app.core.database import get_db
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonProgress
from app.models.student import Student
from app.models.user import User
from app.schemas.b2b import (
    B2BAcademicSummary,
    B2BCertificate,
    B2BClass,
    B2BClassDetail,
    B2BCourse,
    B2BCourseDetail,
    B2BCourseProgress,
    B2BEnrollment,
    B2BEnrollmentDetail,
    B2BPageMeta,
    B2BPageResponse,
    B2BStudent,
    B2BStudentDetail,
)

router = APIRouter()


def _b2b_tenant(client: B2BClient) -> UUID:
    return client.tenant_id


# ---- Summary ----

@router.get("/summary", response_model=B2BAcademicSummary)
async def academic_summary(
    client: B2BClient = Depends(require_b2b_scope("academic:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BAcademicSummary:
    """Aggregated academic KPIs for the Central WR dashboard."""
    tid = _b2b_tenant(client)

    active_courses = int(await db.scalar(
        select(func.count()).select_from(Course).where(
            Course.tenant_id == tid, Course.is_active.is_(True)
        )
    ) or 0)

    active_classes = int(await db.scalar(
        select(func.count()).select_from(Class).where(
            Class.tenant_id == tid, Class.status.in_([ClassStatus.ABERTA.value, ClassStatus.EM_ANDAMENTO.value])
        )
    ) or 0)

    classes_in_progress = int(await db.scalar(
        select(func.count()).select_from(Class).where(
            Class.tenant_id == tid, Class.status == ClassStatus.EM_ANDAMENTO.value
        )
    ) or 0)

    active_students = int(await db.scalar(
        select(func.count(func.distinct(Enrollment.student_id)))
        .select_from(Enrollment)
        .where(
            Enrollment.tenant_id == tid,
            Enrollment.status.in_([EnrollmentStatus.PENDENTE.value, EnrollmentStatus.CONFIRMADA.value]),
        )
    ) or 0)

    active_enrollments = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid,
            Enrollment.status.in_([EnrollmentStatus.PENDENTE.value, EnrollmentStatus.CONFIRMADA.value]),
        )
    ) or 0)

    completed_enrollments = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid, Enrollment.status == EnrollmentStatus.CONCLUIDA.value
        )
    ) or 0)

    certificates_issued = int(await db.scalar(
        select(func.count()).select_from(Certificate).where(
            Certificate.tenant_id == tid, Certificate.status == "ACTIVE"
        )
    ) or 0)

    # Average progress across all active enrollments
    total_lessons = int(await db.scalar(
        select(func.count()).select_from(Lesson).where(Lesson.tenant_id == tid)
    ) or 0)
    completed_lessons = int(await db.scalar(
        select(func.count()).select_from(LessonProgress).where(
            LessonProgress.tenant_id == tid, LessonProgress.completed.is_(True)
        )
    ) or 0)
    avg_progress = round((completed_lessons / total_lessons * 100), 1) if total_lessons > 0 else 0.0

    return B2BAcademicSummary(
        active_courses=active_courses,
        active_classes=active_classes,
        active_students=active_students,
        active_enrollments=active_enrollments,
        completed_enrollments=completed_enrollments,
        certificates_issued=certificates_issued,
        avg_progress_percent=avg_progress,
        classes_in_progress=classes_in_progress,
    )


# ---- Courses ----

@router.get("/courses", response_model=B2BPageResponse)
async def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    client: B2BClient = Depends(require_b2b_scope("academic:read", "courses:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BPageResponse:
    tid = _b2b_tenant(client)
    q = select(Course).where(Course.tenant_id == tid)
    if search:
        q = q.where(Course.name.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.where(Course.is_active.is_(is_active))
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Course.created_at.desc()).offset(skip).limit(limit))).scalars().all()

    data = []
    for c in rows:
        classes_count = int(await db.scalar(
            select(func.count()).select_from(Class).where(
                Class.tenant_id == tid, Class.course_id == c.id
            )
        ) or 0)
        students_count = int(await db.scalar(
            select(func.count(func.distinct(Enrollment.student_id)))
            .select_from(Enrollment)
            .join(Class, Class.id == Enrollment.class_id)
            .where(Class.tenant_id == tid, Class.course_id == c.id)
        ) or 0)
        data.append(B2BCourse(
            id=c.id, code=c.code, name=c.name, category=c.category,
            carga_horaria=c.carga_horaria, modality=c.modality.value,
            is_active=c.is_active, classes_count=classes_count,
            students_count=students_count, created_at=c.created_at,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/courses/{course_id}", response_model=B2BCourseDetail)
async def get_course(
    course_id: UUID,
    client: B2BClient = Depends(require_b2b_scope("academic:read", "courses:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BCourseDetail:
    tid = _b2b_tenant(client)
    c = await db.scalar(select(Course).where(Course.tenant_id == tid, Course.id == course_id))
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    classes_count = int(await db.scalar(
        select(func.count()).select_from(Class).where(
            Class.tenant_id == tid, Class.course_id == c.id
        )
    ) or 0)
    enrollments_count = int(await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Class, Class.id == Enrollment.class_id)
        .where(Class.tenant_id == tid, Class.course_id == c.id)
    ) or 0)
    return B2BCourseDetail(
        id=c.id, code=c.code, name=c.name, category=c.category,
        description=c.description, carga_horaria=c.carga_horaria,
        modality=c.modality.value, tipo_curso=c.tipo_curso.value,
        price=c.price, is_active=c.is_active,
        classes_count=classes_count, enrollments_count=enrollments_count,
        created_at=c.created_at,
    )


# ---- Classes ----

@router.get("/classes", response_model=B2BPageResponse)
async def list_classes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    course_id: UUID | None = Query(None),
    client: B2BClient = Depends(require_b2b_scope("academic:read", "classes:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BPageResponse:
    tid = _b2b_tenant(client)
    q = select(Class, Course).join(Course, Course.id == Class.course_id).where(Class.tenant_id == tid)
    if status_filter:
        q = q.where(Class.status == status_filter.upper())
    if course_id:
        q = q.where(Class.course_id == course_id)
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Class.start_date.desc()).offset(skip).limit(limit))).all()

    data = []
    for cls, course in rows:
        enrollments_count = int(await db.scalar(
            select(func.count()).select_from(Enrollment).where(
                Enrollment.tenant_id == tid, Enrollment.class_id == cls.id
            )
        ) or 0)
        # Company name from first enrollment's student
        company_name = None
        company_row = await db.scalar(
            select(Student.company)
            .select_from(Enrollment)
            .join(Student, Student.id == Enrollment.student_id)
            .where(Enrollment.tenant_id == tid, Enrollment.class_id == cls.id, Student.company.isnot(None))
            .limit(1)
        )
        if company_row:
            company_name = company_row
        data.append(B2BClass(
            id=cls.id, course_id=cls.course_id, course_name=course.name,
            status=cls.status.value, start_date=cls.start_date, end_date=cls.end_date,
            max_students=cls.max_students, location=cls.location,
            enrollments_count=enrollments_count, company_name=company_name,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/classes/{class_id}", response_model=B2BClassDetail)
async def get_class(
    class_id: UUID,
    client: B2BClient = Depends(require_b2b_scope("academic:read", "classes:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BClassDetail:
    tid = _b2b_tenant(client)
    row = await db.scalar(
        select(Class).where(Class.tenant_id == tid, Class.id == class_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    course = await db.scalar(select(Course).where(Course.id == row.course_id))
    enrollments_count = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid, Enrollment.class_id == row.id
        )
    ) or 0)
    completed_count = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid, Enrollment.class_id == row.id,
            Enrollment.status == EnrollmentStatus.CONCLUIDA.value
        )
    ) or 0)
    company_name = None
    company_row = await db.scalar(
        select(Student.company)
        .select_from(Enrollment)
        .join(Student, Student.id == Enrollment.student_id)
        .where(Enrollment.tenant_id == tid, Enrollment.class_id == row.id, Student.company.isnot(None))
        .limit(1)
    )
    if company_row:
        company_name = company_row
    return B2BClassDetail(
        id=row.id, course_id=row.course_id, course_name=course.name if course else "",
        status=row.status.value, start_date=row.start_date, end_date=row.end_date,
        max_students=row.max_students, location=row.location, description=row.description,
        enrollments_count=enrollments_count, completed_count=completed_count,
        company_name=company_name,
    )


# ---- Students ----

@router.get("/students", response_model=B2BPageResponse)
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    company: str | None = Query(None),
    client: B2BClient = Depends(require_b2b_scope("academic:read", "students:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BPageResponse:
    tid = _b2b_tenant(client)
    q = select(Student, User).join(User, User.id == Student.user_id).where(Student.tenant_id == tid)
    if search:
        q = q.where(User.full_name.ilike(f"%{search}%"))
    if company:
        q = q.where(Student.company.ilike(f"%{company}%"))
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Student.created_at.desc()).offset(skip).limit(limit))).all()

    data = []
    for student, user in rows:
        enrollments_count = int(await db.scalar(
            select(func.count()).select_from(Enrollment).where(
                Enrollment.tenant_id == tid, Enrollment.student_id == student.id
            )
        ) or 0)
        status = "active" if user.is_active else "inactive"
        data.append(B2BStudent(
            id=student.id, full_name=user.full_name or "",
            email=user.email, status=status,
            company=student.company, enrollments_count=enrollments_count,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/students/{student_id}", response_model=B2BStudentDetail)
async def get_student(
    student_id: UUID,
    client: B2BClient = Depends(require_b2b_scope("academic:read", "students:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BStudentDetail:
    tid = _b2b_tenant(client)
    row = await db.scalar(
        select(Student).where(Student.tenant_id == tid, Student.id == student_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    user = await db.scalar(select(User).where(User.id == row.user_id))
    enrollments_count = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid, Enrollment.student_id == row.id
        )
    ) or 0)
    completed_count = int(await db.scalar(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tid, Enrollment.student_id == row.id,
            Enrollment.status == EnrollmentStatus.CONCLUIDA.value
        )
    ) or 0)
    certificates_count = int(await db.scalar(
        select(func.count())
        .select_from(Certificate)
        .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
        .where(Certificate.tenant_id == tid, Enrollment.student_id == row.id, Certificate.status == "ACTIVE")
    ) or 0)
    return B2BStudentDetail(
        id=row.id, full_name=user.full_name if user else "",
        email=user.email if user else None, company=row.company,
        enrollments_count=enrollments_count, completed_count=completed_count,
        certificates_count=certificates_count,
    )


# ---- Enrollments ----

@router.get("/enrollments", response_model=B2BPageResponse)
async def list_enrollments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    course_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    student_id: UUID | None = Query(None),
    client: B2BClient = Depends(require_b2b_scope("academic:read", "enrollments:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BPageResponse:
    tid = _b2b_tenant(client)
    q = (
        select(Enrollment, Student, User, Class, Course)
        .join(Student, Student.id == Enrollment.student_id)
        .join(User, User.id == Student.user_id)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Course, Course.id == Class.course_id)
        .where(Enrollment.tenant_id == tid)
    )
    if status_filter:
        q = q.where(Enrollment.status == status_filter.upper())
    if course_id:
        q = q.where(Class.course_id == course_id)
    if class_id:
        q = q.where(Enrollment.class_id == class_id)
    if student_id:
        q = q.where(Enrollment.student_id == student_id)
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Enrollment.enrollment_date.desc()).offset(skip).limit(limit))).all()

    data = []
    for enr, student, user, cls, course in rows:
        # Calculate progress for this enrollment
        lessons_total = int(await db.scalar(
            select(func.count()).select_from(Lesson).where(
                Lesson.tenant_id == tid, Lesson.course_id == course.id
            )
        ) or 0)
        lessons_completed = int(await db.scalar(
            select(func.count())
            .select_from(LessonProgress)
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .where(
                LessonProgress.tenant_id == tid, LessonProgress.student_id == student.id,
                Lesson.course_id == course.id, LessonProgress.completed.is_(True)
            )
        ) or 0)
        progress = round((lessons_completed / lessons_total * 100), 1) if lessons_total > 0 else 0.0
        data.append(B2BEnrollment(
            id=enr.id, student_id=student.id, student_name=user.full_name or "",
            course_name=course.name, class_id=cls.id,
            status=enr.status.value, source=enr.source.value,
            enrollment_date=enr.enrollment_date, progress_percent=progress,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/enrollments/{enrollment_id}", response_model=B2BEnrollmentDetail)
async def get_enrollment(
    enrollment_id: UUID,
    client: B2BClient = Depends(require_b2b_scope("academic:read", "enrollments:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BEnrollmentDetail:
    tid = _b2b_tenant(client)
    row = await db.scalar(
        select(Enrollment).where(Enrollment.tenant_id == tid, Enrollment.id == enrollment_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    student = await db.scalar(select(Student).where(Student.id == row.student_id))
    user = await db.scalar(select(User).where(User.id == student.user_id)) if student else None
    cls = await db.scalar(select(Class).where(Class.id == row.class_id))
    course = await db.scalar(select(Course).where(Course.id == cls.course_id)) if cls else None
    lessons_total = int(await db.scalar(
        select(func.count()).select_from(Lesson).where(
            Lesson.tenant_id == tid, Lesson.course_id == course.id
        )
    ) or 0) if course else 0
    lessons_completed = int(await db.scalar(
        select(func.count())
        .select_from(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            LessonProgress.tenant_id == tid, LessonProgress.student_id == student.id,
            Lesson.course_id == course.id, LessonProgress.completed.is_(True)
        )
    ) or 0) if course and student else 0
    progress = round((lessons_completed / lessons_total * 100), 1) if lessons_total > 0 else 0.0
    return B2BEnrollmentDetail(
        id=row.id, student_id=student.id if student else None,
        student_name=user.full_name if user else "",
        course_id=course.id if course else None, course_name=course.name if course else "",
        class_id=cls.id if cls else None, status=row.status.value,
        source=row.source.value, enrollment_date=row.enrollment_date,
        lessons_completed=lessons_completed, lessons_total=lessons_total,
        progress_percent=progress,
    )


# ---- Certificates ----

@router.get("/certificates", response_model=B2BPageResponse)
async def list_certificates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    student_id: UUID | None = Query(None),
    client: B2BClient = Depends(require_b2b_scope("academic:read", "certificates:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BPageResponse:
    tid = _b2b_tenant(client)
    q = (
        select(Certificate, Enrollment, Student, User, Class, Course)
        .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
        .join(Student, Student.id == Enrollment.student_id)
        .join(User, User.id == Student.user_id)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Course, Course.id == Class.course_id)
        .where(Certificate.tenant_id == tid)
    )
    if status_filter:
        q = q.where(Certificate.status == status_filter.upper())
    if student_id:
        q = q.where(Enrollment.student_id == student_id)
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Certificate.issued_at.desc()).offset(skip).limit(limit))).all()

    data = []
    for cert, enr, student, user, cls, course in rows:
        data.append(B2BCertificate(
            id=cert.id, student_name=user.full_name or "",
            course_name=course.name, certificate_number=cert.certificate_number,
            validation_code=cert.validation_code, issued_at=cert.issued_at,
            expires_at=cert.expires_at, status=cert.status,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


# ---- Course progress (aggregated) ----

@router.get("/courses/{course_id}/progress", response_model=B2BCourseProgress)
async def course_progress(
    course_id: UUID,
    client: B2BClient = Depends(require_b2b_scope("academic:read")),
    db: AsyncSession = Depends(get_db),
) -> B2BCourseProgress:
    tid = _b2b_tenant(client)
    course = await db.scalar(select(Course).where(Course.tenant_id == tid, Course.id == course_id))
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    total_enrollments = int(await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Class, Class.id == Enrollment.class_id)
        .where(Class.tenant_id == tid, Class.course_id == course_id)
    ) or 0)
    completed = int(await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Class.tenant_id == tid, Class.course_id == course_id,
            Enrollment.status == EnrollmentStatus.CONCLUIDA.value
        )
    ) or 0)
    in_progress = total_enrollments - completed
    lessons_total = int(await db.scalar(
        select(func.count()).select_from(Lesson).where(
            Lesson.tenant_id == tid, Lesson.course_id == course_id
        )
    ) or 0)
    completed_lessons = int(await db.scalar(
        select(func.count())
        .select_from(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            Lesson.tenant_id == tid, Lesson.course_id == course_id,
            LessonProgress.completed.is_(True)
        )
    ) or 0)
    avg_progress = round((completed_lessons / lessons_total * 100), 1) if lessons_total > 0 else 0.0
    return B2BCourseProgress(
        course_id=course.id, course_name=course.name,
        total_enrollments=total_enrollments, completed=completed,
        in_progress=in_progress, avg_progress_percent=avg_progress,
    )
