"""B2B read-only academic API for Central WR integration.

All endpoints require B2B client credentials (X-B2B-Client-Id +
X-B2B-Client-Secret) and appropriate scopes. Data is tenant-scoped
to the B2B client's registered tenant via RLS.

Key design:
- ``get_b2b_db`` provides a session with ``app.current_tenant`` set
  to the client's tenant_id (parameterized, no string interpolation).
- ``academic:read`` is a superset scope granting access to all
  academic endpoints. Specific scopes (``courses:read``, etc.) grant
  access only to their respective endpoints.
- All responses are LGPD-safe: no CPF, password_hash, tokens, or
  client_secret_hash are ever returned.
- N+1 queries in list endpoints are eliminated via subquery aggregation.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Numeric, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.b2b_security import B2BContext, get_b2b_db, require_b2b_scope
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonProgress
from app.models.student import Student
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.b2b import (
    B2BAcademicSummary,
    B2BCertificate,
    B2BClass,
    B2BClassDetail,
    B2BContextResponse,
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


# ---- Context (for binding verification) ----

@router.get("/context", response_model=B2BContextResponse)
async def b2b_context(
    ctx: B2BContext = Depends(require_b2b_scope("academic:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BContextResponse:
    """Return the authenticated B2B client's context (no secret).

    Used by Central WR to verify that the LMS tenant binding matches
    the credential's actual tenant. This prevents a misconfigured
    binding from serving data from the wrong LMS tenant.
    """
    tenant = await db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id))
    return B2BContextResponse(
        tenant_id=ctx.tenant_id,
        tenant_slug=tenant.slug if tenant else None,
        client_id=ctx.client.client_id,
        scopes=sorted(ctx.scopes),
        api_version="1",
    )


# ---- Summary ----

@router.get("/summary", response_model=B2BAcademicSummary)
async def academic_summary(
    ctx: B2BContext = Depends(require_b2b_scope("academic:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BAcademicSummary:
    """Aggregated academic KPIs for the Central WR dashboard."""
    tid = ctx.tenant_id

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

    # Average progress: mean of per-enrollment progress percentages.
    # For each active enrollment, progress = completed_lessons / total_lessons * 100.
    # We compute this in a single query using subqueries, then average.
    # This guarantees 0 <= avg_progress <= 100.
    avg_progress = await _compute_avg_progress(db, tid)

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


async def _compute_enrollment_progress(
    db: AsyncSession, tid: UUID, student_id: UUID, course_id: UUID
) -> float:
    """Compute progress percentage for a single enrollment (required-only).

    Uses the canonical required-only rule: completed_required / required_lessons.
    Returns 0.0 if the course has no required lessons. Result is always 0 <= p <= 100.
    """
    from app.services.progress_service import compute_progress_percentage
    return await compute_progress_percentage(db, tid, course_id, student_id)


async def _compute_avg_progress(db: AsyncSession, tid: UUID) -> float:
    """Compute average progress across all active enrollments.

    For each enrollment (PENDENTE or CONFIRMADA), computes individual
    progress = completed_lessons / total_lessons * 100, then averages.
    Returns 0.0 if there are no active enrollments.
    Always returns a value in [0, 100].
    """
    # Get all active enrollments with their student_id and course_id
    rows = (await db.execute(
        select(Enrollment.student_id, Class.course_id)
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Enrollment.tenant_id == tid,
            Class.tenant_id == tid,
            Enrollment.status.in_([EnrollmentStatus.PENDENTE.value, EnrollmentStatus.CONFIRMADA.value]),
        )
    )).all()

    if not rows:
        return 0.0

    # Compute per-enrollment progress using a single aggregated query
    # to avoid N+1. We join enrollments → classes → courses → lessons
    # and lessons → lesson_progress, then compute progress per enrollment.
    progress_subq = (
        select(
            Enrollment.id.label("enrollment_id"),
            Enrollment.student_id,
            Class.course_id,
        )
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Enrollment.tenant_id == tid,
            Class.tenant_id == tid,
            Enrollment.status.in_([EnrollmentStatus.PENDENTE.value, EnrollmentStatus.CONFIRMADA.value]),
        )
        .subquery()
    )

    lessons_total_subq = (
        select(
            Lesson.course_id,
            func.count(Lesson.id).label("total_lessons"),
        )
        .where(Lesson.tenant_id == tid, Lesson.is_required.is_(True))
        .group_by(Lesson.course_id)
        .subquery()
    )

    lessons_completed_subq = (
        select(
            LessonProgress.student_id,
            Lesson.course_id,
            func.count(LessonProgress.id).label("completed_lessons"),
        )
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            LessonProgress.tenant_id == tid,
            LessonProgress.completed.is_(True),
            Lesson.is_required.is_(True),
        )
        .group_by(LessonProgress.student_id, Lesson.course_id)
        .subquery()
    )

    # Per-enrollment progress = COALESCE(completed, 0) / total * 100
    per_enrollment = (
        select(
            progress_subq.c.enrollment_id,
            func.round(
                (func.coalesce(lessons_completed_subq.c.completed_lessons, 0)
                * 100.0
                / func.nullif(lessons_total_subq.c.total_lessons, 0)).cast(Numeric),
                1,
            ).label("progress"),
        )
        .select_from(progress_subq)
        .outerjoin(lessons_total_subq, lessons_total_subq.c.course_id == progress_subq.c.course_id)
        .outerjoin(
            lessons_completed_subq,
            (lessons_completed_subq.c.student_id == progress_subq.c.student_id)
            & (lessons_completed_subq.c.course_id == progress_subq.c.course_id),
        )
    ).subquery()

    # Average of per-enrollment progress, treating NULL (no lessons) as 0
    avg = await db.scalar(
        select(func.avg(func.coalesce(per_enrollment.c.progress, 0.0)))
    )
    if avg is None:
        return 0.0
    return round(min(float(avg), 100.0), 1)


# ---- Courses ----

@router.get("/courses", response_model=B2BPageResponse[B2BCourse])
async def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "courses:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BPageResponse:
    tid = ctx.tenant_id
    q = select(Course).where(Course.tenant_id == tid)
    if search:
        q = q.where(Course.name.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.where(Course.is_active.is_(is_active))
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Course.created_at.desc()).offset(skip).limit(limit))).scalars().all()

    # N+1 elimination: batch counts for all courses in a single query
    course_ids = [c.id for c in rows]
    classes_counts = {}
    students_counts = {}
    if course_ids:
        classes_subq = (
            select(Class.course_id, func.count(Class.id).label("cnt"))
            .where(Class.tenant_id == tid, Class.course_id.in_(course_ids))
            .group_by(Class.course_id)
        )
        for row in (await db.execute(classes_subq)).all():
            classes_counts[row.course_id] = int(row.cnt)

        students_subq = (
            select(Class.course_id, func.count(func.distinct(Enrollment.student_id)).label("cnt"))
            .select_from(Enrollment)
            .join(Class, Class.id == Enrollment.class_id)
            .where(
                Class.tenant_id == tid,
                Enrollment.tenant_id == tid,
                Class.course_id.in_(course_ids),
            )
            .group_by(Class.course_id)
        )
        for row in (await db.execute(students_subq)).all():
            students_counts[row.course_id] = int(row.cnt)

    data = []
    for c in rows:
        data.append(B2BCourse(
            id=c.id, code=c.code, name=c.name, category=c.category,
            carga_horaria=c.carga_horaria, modality=c.modality.value,
            is_active=c.is_active, classes_count=classes_counts.get(c.id, 0),
            students_count=students_counts.get(c.id, 0), created_at=c.created_at,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/courses/{course_id}", response_model=B2BCourseDetail)
async def get_course(
    course_id: UUID,
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "courses:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BCourseDetail:
    tid = ctx.tenant_id
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
        .where(
            Class.tenant_id == tid,
            Enrollment.tenant_id == tid,
            Class.course_id == c.id,
        )
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

@router.get("/classes", response_model=B2BPageResponse[B2BClass])
async def list_classes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    course_id: UUID | None = Query(None),
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "classes:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BPageResponse:
    tid = ctx.tenant_id
    q = select(Class, Course).join(Course, Course.id == Class.course_id).where(
        Class.tenant_id == tid, Course.tenant_id == tid
    )
    if status_filter:
        q = q.where(Class.status == status_filter.upper())
    if course_id:
        q = q.where(Class.course_id == course_id)
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Class.start_date.desc()).offset(skip).limit(limit))).all()

    # N+1 elimination: batch enrollment counts and company names
    class_ids = [cls.id for cls, _ in rows]
    enrollments_counts = {}
    company_names = {}
    if class_ids:
        enr_subq = (
            select(Enrollment.class_id, func.count(Enrollment.id).label("cnt"))
            .where(Enrollment.tenant_id == tid, Enrollment.class_id.in_(class_ids))
            .group_by(Enrollment.class_id)
        )
        for row in (await db.execute(enr_subq)).all():
            enrollments_counts[row.class_id] = int(row.cnt)

        # Company name: first non-null company per class
        company_subq = (
            select(Enrollment.class_id, Student.company)
            .select_from(Enrollment)
            .join(Student, Student.id == Enrollment.student_id)
            .where(
                Enrollment.tenant_id == tid,
                Student.tenant_id == tid,
                Enrollment.class_id.in_(class_ids),
                Student.company.isnot(None),
            )
            .distinct(Enrollment.class_id)
        )
        for row in (await db.execute(company_subq)).all():
            if row.class_id not in company_names:
                company_names[row.class_id] = row.company

    data = []
    for cls, course in rows:
        data.append(B2BClass(
            id=cls.id, course_id=cls.course_id, course_name=course.name,
            status=cls.status.value, start_date=cls.start_date, end_date=cls.end_date,
            max_students=cls.max_students, location=cls.location,
            enrollments_count=enrollments_counts.get(cls.id, 0),
            company_name=company_names.get(cls.id),
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/classes/{class_id}", response_model=B2BClassDetail)
async def get_class(
    class_id: UUID,
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "classes:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BClassDetail:
    tid = ctx.tenant_id
    row = await db.scalar(
        select(Class).where(Class.tenant_id == tid, Class.id == class_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    course = await db.scalar(select(Course).where(Course.tenant_id == tid, Course.id == row.course_id))
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
        .where(
            Enrollment.tenant_id == tid,
            Student.tenant_id == tid,
            Enrollment.class_id == row.id,
            Student.company.isnot(None),
        )
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

@router.get("/students", response_model=B2BPageResponse[B2BStudent])
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    company: str | None = Query(None),
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "students:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BPageResponse:
    tid = ctx.tenant_id
    q = select(Student, User).join(User, User.id == Student.user_id).where(
        Student.tenant_id == tid, User.tenant_id == tid
    )
    if search:
        q = q.where(User.full_name.ilike(f"%{search}%"))
    if company:
        q = q.where(Student.company.ilike(f"%{company}%"))
    total = int(await db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = (await db.execute(q.order_by(Student.created_at.desc()).offset(skip).limit(limit))).all()

    # N+1 elimination: batch enrollment counts
    student_ids = [s.id for s, _ in rows]
    enrollments_counts = {}
    if student_ids:
        enr_subq = (
            select(Enrollment.student_id, func.count(Enrollment.id).label("cnt"))
            .where(Enrollment.tenant_id == tid, Enrollment.student_id.in_(student_ids))
            .group_by(Enrollment.student_id)
        )
        for row in (await db.execute(enr_subq)).all():
            enrollments_counts[row.student_id] = int(row.cnt)

    data = []
    for student, user in rows:
        status_val = "active" if user.is_active else "inactive"
        data.append(B2BStudent(
            id=student.id, full_name=user.full_name or "",
            email=user.email, status=status_val,
            company=student.company, enrollments_count=enrollments_counts.get(student.id, 0),
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


@router.get("/students/{student_id}", response_model=B2BStudentDetail)
async def get_student(
    student_id: UUID,
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "students:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BStudentDetail:
    tid = ctx.tenant_id
    row = await db.scalar(
        select(Student).where(Student.tenant_id == tid, Student.id == student_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    user = await db.scalar(select(User).where(User.tenant_id == tid, User.id == row.user_id))
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
        .where(
            Certificate.tenant_id == tid,
            Enrollment.tenant_id == tid,
            Enrollment.student_id == row.id,
            Certificate.status == "ACTIVE",
        )
    ) or 0)
    return B2BStudentDetail(
        id=row.id, full_name=user.full_name if user else "",
        email=user.email if user else None, company=row.company,
        enrollments_count=enrollments_count, completed_count=completed_count,
        certificates_count=certificates_count,
    )


# ---- Enrollments ----

@router.get("/enrollments", response_model=B2BPageResponse[B2BEnrollment])
async def list_enrollments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    course_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    student_id: UUID | None = Query(None),
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "enrollments:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BPageResponse:
    tid = ctx.tenant_id
    q = (
        select(Enrollment, Student, User, Class, Course)
        .join(Student, Student.id == Enrollment.student_id)
        .join(User, User.id == Student.user_id)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Course, Course.id == Class.course_id)
        .where(
            Enrollment.tenant_id == tid,
            Student.tenant_id == tid,
            User.tenant_id == tid,
            Class.tenant_id == tid,
            Course.tenant_id == tid,
        )
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

    # N+1 elimination: batch progress computation for all enrollments
    enr_progress = {}
    if rows:
        enr_progress = await _batch_compute_progress(db, tid, rows)

    data = []
    for enr, student, user, cls, course in rows:
        progress = enr_progress.get(enr.id, 0.0)
        data.append(B2BEnrollment(
            id=enr.id, student_id=student.id, student_name=user.full_name or "",
            course_name=course.name, class_id=cls.id,
            status=enr.status.value, source=enr.source.value,
            enrollment_date=enr.enrollment_date, progress_percent=progress,
        ))
    return B2BPageResponse(meta=B2BPageMeta(skip=skip, limit=limit, total=total), data=data)


async def _batch_compute_progress(
    db: AsyncSession, tid: UUID, rows: list
) -> dict[UUID, float]:
    """Batch-compute progress for multiple enrollments.

    Returns a dict mapping enrollment_id → progress_percent (0-100).
    Uses a single aggregated query instead of N individual queries.
    """
    # Collect (enrollment_id, student_id, course_id) tuples
    entries = [(enr.id, student.id, course.id) for enr, student, _, _, course in rows]
    if not entries:
        return {}

    student_ids = list({s for _, s, _ in entries})
    course_ids = list({c for _, _, c in entries})

    # Total lessons per course
    total_subq = (
        select(Lesson.course_id, func.count(Lesson.id).label("total"))
        .where(Lesson.tenant_id == tid, Lesson.course_id.in_(course_ids))
        .group_by(Lesson.course_id)
    ).subquery()

    # Completed lessons per (student, course)
    completed_subq = (
        select(LessonProgress.student_id, Lesson.course_id, func.count(LessonProgress.id).label("completed"))
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            LessonProgress.tenant_id == tid,
            LessonProgress.completed.is_(True),
            LessonProgress.student_id.in_(student_ids),
            Lesson.course_id.in_(course_ids),
        )
        .group_by(LessonProgress.student_id, Lesson.course_id)
    ).subquery()

    # Build a lookup: (student_id, course_id) → progress
    progress_lookup: dict[tuple[UUID, UUID], float] = {}

    # Get totals
    totals: dict[UUID, int] = {}
    for row in (await db.execute(select(total_subq.c.course_id, total_subq.c.total))).all():
        totals[row.course_id] = int(row.total)

    # Get completed
    completed: dict[tuple[UUID, UUID], int] = {}
    for row in (await db.execute(
        select(completed_subq.c.student_id, completed_subq.c.course_id, completed_subq.c.completed)
    )).all():
        completed[(row.student_id, row.course_id)] = int(row.completed)

    for enr_id, student_id, course_id in entries:
        total = totals.get(course_id, 0)
        if total == 0:
            progress_lookup.setdefault((student_id, course_id), 0.0)
            continue
        comp = completed.get((student_id, course_id), 0)
        pct = round(min(comp / total * 100, 100.0), 1)
        progress_lookup[(student_id, course_id)] = pct

    return {enr_id: progress_lookup.get((sid, cid), 0.0) for enr_id, sid, cid in entries}


@router.get("/enrollments/{enrollment_id}", response_model=B2BEnrollmentDetail)
async def get_enrollment(
    enrollment_id: UUID,
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "enrollments:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BEnrollmentDetail:
    tid = ctx.tenant_id
    row = await db.scalar(
        select(Enrollment).where(Enrollment.tenant_id == tid, Enrollment.id == enrollment_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    student = await db.scalar(select(Student).where(Student.tenant_id == tid, Student.id == row.student_id))
    user = await db.scalar(select(User).where(User.tenant_id == tid, User.id == student.user_id)) if student else None
    cls = await db.scalar(select(Class).where(Class.tenant_id == tid, Class.id == row.class_id))
    # If the class is not in this tenant (cross-tenant FK), fail closed.
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment class not found")
    course = await db.scalar(select(Course).where(Course.tenant_id == tid, Course.id == cls.course_id))
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment course not found")
    lessons_total = int(await db.scalar(
        select(func.count()).select_from(Lesson).where(
            Lesson.tenant_id == tid, Lesson.course_id == course.id,
            Lesson.is_required.is_(True),
        )
    ) or 0) if course else 0
    lessons_completed = int(await db.scalar(
        select(func.count())
        .select_from(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            LessonProgress.tenant_id == tid, LessonProgress.student_id == student.id,
            Lesson.course_id == course.id, LessonProgress.completed.is_(True),
            Lesson.is_required.is_(True),
        )
    ) or 0) if course and student else 0
    progress = round(min(lessons_completed / lessons_total * 100, 100.0), 1) if lessons_total > 0 else 0.0
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

@router.get("/certificates", response_model=B2BPageResponse[B2BCertificate])
async def list_certificates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None),
    student_id: UUID | None = Query(None),
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "certificates:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BPageResponse:
    tid = ctx.tenant_id
    q = (
        select(Certificate, Enrollment, Student, User, Class, Course)
        .join(Enrollment, Enrollment.id == Certificate.enrollment_id)
        .join(Student, Student.id == Enrollment.student_id)
        .join(User, User.id == Student.user_id)
        .join(Class, Class.id == Enrollment.class_id)
        .join(Course, Course.id == Class.course_id)
        .where(
            Certificate.tenant_id == tid,
            Enrollment.tenant_id == tid,
            Student.tenant_id == tid,
            User.tenant_id == tid,
            Class.tenant_id == tid,
            Course.tenant_id == tid,
        )
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
    ctx: B2BContext = Depends(require_b2b_scope("academic:read", "courses:read")),
    db: AsyncSession = Depends(get_b2b_db),
) -> B2BCourseProgress:
    tid = ctx.tenant_id
    course = await db.scalar(select(Course).where(Course.tenant_id == tid, Course.id == course_id))
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    enrollment_scope = (
        select(Enrollment.status)
        .select_from(Enrollment)
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Class.tenant_id == tid,
            Enrollment.tenant_id == tid,
            Class.course_id == course_id,
        )
        .subquery()
    )
    total_enrollments = int(await db.scalar(
        select(func.count()).select_from(enrollment_scope)
    ) or 0)
    completed = int(await db.scalar(
        select(func.count()).select_from(enrollment_scope).where(
            enrollment_scope.c.status == EnrollmentStatus.CONCLUIDA.value,
        )
    ) or 0)
    # Explicit status taxonomy: cancelled/other terminal records are not
    # considered in progress. Never derive this as total - completed.
    in_progress = int(await db.scalar(
        select(func.count()).select_from(enrollment_scope).where(
            enrollment_scope.c.status.in_([
                EnrollmentStatus.PENDENTE.value,
                EnrollmentStatus.CONFIRMADA.value,
            ])
        )
    ) or 0)

    # Average progress: mean of per-enrollment progress for this course
    # Get all enrollments for this course
    enr_rows = (await db.execute(
        select(Enrollment.student_id)
        .join(Class, Class.id == Enrollment.class_id)
        .where(
            Class.tenant_id == tid,
            Enrollment.tenant_id == tid,
            Class.course_id == course_id,
        )
    )).all()

    if not enr_rows:
        avg_progress = 0.0
    else:
        # Batch compute progress for all enrollments in this course
        student_ids = [r.student_id for r in enr_rows]
        lessons_total = int(await db.scalar(
            select(func.count()).select_from(Lesson).where(
                Lesson.tenant_id == tid, Lesson.course_id == course_id,
                Lesson.is_required.is_(True),
            )
        ) or 0)
        if lessons_total == 0:
            avg_progress = 0.0
        else:
            completed_per_student = (await db.execute(
                select(LessonProgress.student_id, func.count(LessonProgress.id).label("cnt"))
                .join(Lesson, Lesson.id == LessonProgress.lesson_id)
                .where(
                    LessonProgress.tenant_id == tid,
                    LessonProgress.completed.is_(True),
                    LessonProgress.student_id.in_(student_ids),
                    Lesson.course_id == course_id,
                    Lesson.is_required.is_(True),
                )
                .group_by(LessonProgress.student_id)
            )).all()
            completed_map = {r.student_id: int(r.cnt) for r in completed_per_student}
            progresses = []
            for sid in student_ids:
                comp = completed_map.get(sid, 0)
                pct = min(comp / lessons_total * 100, 100.0)
                progresses.append(pct)
            avg_progress = round(sum(progresses) / len(progresses), 1) if progresses else 0.0

    return B2BCourseProgress(
        course_id=course.id, course_name=course.name,
        total_enrollments=total_enrollments, completed=completed,
        in_progress=in_progress, avg_progress_percent=avg_progress,
    )
