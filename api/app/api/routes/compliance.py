from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.proxy import get_client_ip
from app.core.security import get_current_admin, get_current_tenant_id, get_current_user
from app.core.utils import utc_now
from app.models.compliance import (
    CourseComplianceProfile,
    PedagogicalProjectVersion,
    PracticalTrainingRecord,
    TrainingAccessEvent,
    TrainingProfessional,
    TrainingSession,
)
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.class_model import Class
from app.models.student import Student
from app.schemas.compliance import (
    ComplianceProfileResponse,
    ComplianceProfileUpdate,
    ComplianceReadinessItem,
    PedagogicalProjectCreate,
    PedagogicalProjectResponse,
    PracticalTrainingCreate,
    SessionHeartbeatResponse,
    SessionStartResponse,
    TrainingProfessionalCreate,
    TrainingProfessionalResponse,
)
from app.services.compliance_service import ComplianceService

router = APIRouter()
_ALLOWED_MODES = {"EAD", "SEMIPRESENCIAL", "PRESENCIAL"}
_ALLOWED_PROFILE_STATUSES = {"DRAFT", "IN_REVIEW", "REVIEW_REQUIRED", "ARCHIVED"}


async def _course(db: AsyncSession, tenant_id: UUID, course_id: UUID) -> Course:
    item = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Course not found")
    return item


async def _profile(db: AsyncSession, tenant_id: UUID, course_id: UUID) -> CourseComplianceProfile:
    item = await ComplianceService.get_profile(db, tenant_id=tenant_id, course_id=course_id)
    if not item:
        raise HTTPException(status_code=404, detail="Compliance profile not found")
    return item


async def _student_context(
    db: AsyncSession, tenant_id: UUID, current_user: dict, course_id: UUID
) -> tuple[Student, Enrollment]:
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    user_id = UUID(current_user["user_id"])
    student = (
        await db.execute(
            select(Student).where(Student.tenant_id == tenant_id, Student.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    enrollment = (
        await db.execute(
            select(Enrollment)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.student_id == student.id,
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
                Enrollment.status.in_([EnrollmentStatus.CONFIRMADA, EnrollmentStatus.CONCLUIDA]),
            )
            .order_by(Enrollment.enrollment_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=403, detail="Active enrollment required")
    return student, enrollment


async def _structural_blockers(
    db: AsyncSession, *, tenant_id: UUID, course: Course, profile: CourseComplianceProfile
) -> list[str]:
    blockers: list[str] = []
    if not profile.regulatory_standard:
        blockers.append("Norma regulamentadora não identificada")
    if not profile.regulatory_version:
        blockers.append("Versão normativa não confirmada")
    if not profile.normative_source_url:
        blockers.append("Fonte oficial não registrada")
    if not profile.required_delivery_mode:
        blockers.append("Modalidade permitida/exigida não confirmada")
    else:
        actual = getattr(course.modality, "value", course.modality)
        if actual != profile.required_delivery_mode:
            blockers.append(
                f"Curso está como {actual}, mas a regra validada exige {profile.required_delivery_mode}"
            )
    if profile.minimum_workload_hours is None:
        blockers.append("Carga horária mínima regulatória não confirmada")
    if profile.requires_final_assessment and not profile.assessment_practical_scenarios_validated:
        blockers.append("Questões práticas da avaliação ainda não foram validadas pelo responsável técnico")
    if not profile.support_channel_verified:
        blockers.append("Canal de dúvidas operacional não validado")

    professional = None
    if profile.technical_responsible_id:
        professional = (
            await db.execute(
                select(TrainingProfessional).where(
                    TrainingProfessional.id == profile.technical_responsible_id,
                    TrainingProfessional.tenant_id == tenant_id,
                    TrainingProfessional.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    if not professional or professional.professional_role != "TECHNICAL_RESPONSIBLE":
        blockers.append("Responsável técnico válido não vinculado")

    project = None
    if profile.pedagogical_project_version_id:
        project = (
            await db.execute(
                select(PedagogicalProjectVersion).where(
                    PedagogicalProjectVersion.id == profile.pedagogical_project_version_id,
                    PedagogicalProjectVersion.tenant_id == tenant_id,
                    PedagogicalProjectVersion.course_id == course.id,
                    PedagogicalProjectVersion.status == "APPROVED",
                )
            )
        ).scalar_one_or_none()
    if not project:
        blockers.append("Projeto pedagógico aprovado não vinculado")
    if profile.blocker_reason:
        blockers.append(profile.blocker_reason)
    return list(dict.fromkeys(blockers))


@router.get("/courses", response_model=list[ComplianceReadinessItem])
async def list_compliance_readiness(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    courses = list(
        (
            await db.execute(
                select(Course).where(Course.tenant_id == tenant_id).order_by(Course.code)
            )
        ).scalars().all()
    )
    profiles = list(
        (
            await db.execute(
                select(CourseComplianceProfile).where(CourseComplianceProfile.tenant_id == tenant_id)
            )
        ).scalars().all()
    )
    by_course = {item.course_id: item for item in profiles}
    response: list[ComplianceReadinessItem] = []
    for course in courses:
        profile = by_course.get(course.id)
        if not profile:
            blockers = ["Perfil regulatório não cadastrado"] if course.code.startswith("NR-") else []
            status_value = "MISSING" if blockers else "NOT_APPLICABLE"
            standard = None
            required_mode = None
        else:
            blockers = await _structural_blockers(
                db, tenant_id=tenant_id, course=course, profile=profile
            )
            if profile.status != "COMPLIANCE_READY":
                blockers.insert(0, f"Status atual: {profile.status}")
            status_value = profile.status
            standard = profile.regulatory_standard
            required_mode = profile.required_delivery_mode
        response.append(
            ComplianceReadinessItem(
                course_id=course.id,
                course_code=course.code,
                course_name=course.name,
                course_modality=getattr(course.modality, "value", course.modality),
                profile_status=status_value,
                regulatory_standard=standard,
                required_delivery_mode=required_mode,
                official_certificate_eligible=not blockers and status_value == "COMPLIANCE_READY",
                blockers=list(dict.fromkeys(blockers)),
            )
        )
    return response


@router.get("/courses/{course_id}", response_model=ComplianceProfileResponse)
async def get_compliance_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    return await _profile(db, tenant_id, course_id)


@router.patch("/courses/{course_id}", response_model=ComplianceProfileResponse)
async def update_compliance_profile(
    course_id: UUID,
    payload: ComplianceProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    profile = await _profile(db, tenant_id, course_id)
    values = payload.model_dump(exclude_unset=True)
    if values.get("required_delivery_mode") and values["required_delivery_mode"] not in _ALLOWED_MODES:
        raise HTTPException(status_code=422, detail="Invalid required_delivery_mode")
    if "technical_responsible_id" in values and values["technical_responsible_id"]:
        professional = (
            await db.execute(
                select(TrainingProfessional).where(
                    TrainingProfessional.id == values["technical_responsible_id"],
                    TrainingProfessional.tenant_id == tenant_id,
                    TrainingProfessional.professional_role == "TECHNICAL_RESPONSIBLE",
                )
            )
        ).scalar_one_or_none()
        if not professional:
            raise HTTPException(status_code=422, detail="Invalid technical responsible")
    if "pedagogical_project_version_id" in values and values["pedagogical_project_version_id"]:
        project = (
            await db.execute(
                select(PedagogicalProjectVersion).where(
                    PedagogicalProjectVersion.id == values["pedagogical_project_version_id"],
                    PedagogicalProjectVersion.tenant_id == tenant_id,
                    PedagogicalProjectVersion.course_id == course_id,
                    PedagogicalProjectVersion.status == "APPROVED",
                )
            )
        ).scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=422, detail="Pedagogical project must be approved")
    for key, value in values.items():
        setattr(profile, key, value)
    profile.status = "IN_REVIEW"
    profile.reviewed_at = None
    profile.reviewed_by = None
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/courses/{course_id}/approve", response_model=ComplianceProfileResponse)
async def approve_compliance_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _course(db, tenant_id, course_id)
    profile = await _profile(db, tenant_id, course_id)
    blockers = await _structural_blockers(db, tenant_id=tenant_id, course=course, profile=profile)
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Compliance profile cannot be approved", "blockers": blockers},
        )
    now = utc_now()
    profile.status = "COMPLIANCE_READY"
    profile.source_checked_at = profile.source_checked_at or now
    profile.reviewed_at = now
    profile.reviewed_by = UUID(current_user["user_id"])
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/professionals", response_model=list[TrainingProfessionalResponse])
async def list_training_professionals(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    return list(
        (
            await db.execute(
                select(TrainingProfessional)
                .where(TrainingProfessional.tenant_id == tenant_id)
                .order_by(TrainingProfessional.full_name)
            )
        ).scalars().all()
    )


@router.post("/professionals", response_model=TrainingProfessionalResponse, status_code=201)
async def create_training_professional(
    payload: TrainingProfessionalCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    role = payload.professional_role.upper()
    if role not in {"INSTRUCTOR", "TECHNICAL_RESPONSIBLE"}:
        raise HTTPException(status_code=422, detail="professional_role must be INSTRUCTOR or TECHNICAL_RESPONSIBLE")
    item = TrainingProfessional(
        tenant_id=tenant_id,
        **{**payload.model_dump(), "professional_role": role},
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.post(
    "/courses/{course_id}/pedagogical-projects",
    response_model=PedagogicalProjectResponse,
    status_code=201,
)
async def create_pedagogical_project(
    course_id: UUID,
    payload: PedagogicalProjectCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    item = PedagogicalProjectVersion(tenant_id=tenant_id, course_id=course_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/pedagogical-projects/{project_id}/approve", response_model=PedagogicalProjectResponse)
async def approve_pedagogical_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    project = (
        await db.execute(
            select(PedagogicalProjectVersion).where(
                PedagogicalProjectVersion.id == project_id,
                PedagogicalProjectVersion.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Pedagogical project not found")
    required = {
        "general_objective": project.general_objective,
        "safety_principles": project.safety_principles,
        "pedagogical_strategy": project.pedagogical_strategy,
        "operational_infrastructure": project.operational_infrastructure,
        "theoretical_program": project.theoretical_program,
        "module_objectives": project.module_objectives,
        "workload_hours": project.workload_hours,
        "target_audience": project.target_audience,
        "teaching_materials": project.teaching_materials,
        "learning_tools": project.learning_tools,
        "assessment_methodology": project.assessment_methodology,
        "support_channel": project.support_channel,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise HTTPException(status_code=409, detail={"message": "Project incomplete", "missing": missing})
    now = utc_now()
    project.status = "APPROVED"
    project.approved_at = now
    project.approved_by = UUID(current_user["user_id"])
    project.valid_until = now + timedelta(days=730)
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/enrollments/{enrollment_id}/practical", status_code=201)
async def record_practical_training(
    enrollment_id: UUID,
    payload: PracticalTrainingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = (
        await db.execute(
            select(Enrollment, Class)
            .join(Class, Enrollment.class_id == Class.id)
            .where(Enrollment.id == enrollment_id, Enrollment.tenant_id == tenant_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    enrollment, class_obj = row
    instructor = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == payload.instructor_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not instructor:
        raise HTTPException(status_code=422, detail="Instructor not found")
    if payload.result not in {"SATISFATORIO", "INSATISFATORIO"}:
        raise HTTPException(status_code=422, detail="Invalid practical result")
    item = PracticalTrainingRecord(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        course_id=class_obj.course_id,
        student_id=enrollment.student_id,
        recorded_by=UUID(current_user["user_id"]),
        **payload.model_dump(),
    )
    db.add(item)
    await db.commit()
    return {"id": str(item.id), "result": item.result}


@router.post("/courses/{course_id}/sessions/start", response_model=SessionStartResponse, status_code=201)
async def start_training_session(
    course_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    student, enrollment = await _student_context(db, tenant_id, current_user, course_id)
    now = utc_now()
    session = TrainingSession(
        tenant_id=tenant_id,
        enrollment_id=enrollment.id,
        student_id=student.id,
        course_id=course_id,
        started_at=now,
        last_heartbeat_at=now,
    )
    db.add(session)
    await db.flush()
    profile = await ComplianceService.get_profile(db, tenant_id=tenant_id, course_id=course_id)
    db.add(
        TrainingAccessEvent(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=course_id,
            event_type="SESSION_STARTED",
            session_id=session.id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            retain_until=ComplianceService.retention_until(profile=profile, occurred_at=now),
        )
    )
    await db.commit()
    await db.refresh(session)
    return SessionStartResponse(session_id=session.id, started_at=session.started_at, active_seconds=0)


@router.post("/sessions/{session_id}/heartbeat", response_model=SessionHeartbeatResponse)
async def heartbeat_training_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    user_id = UUID(current_user["user_id"])
    student = (
        await db.execute(
            select(Student).where(Student.tenant_id == tenant_id, Student.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    session = (
        await db.execute(
            select(TrainingSession).where(
                TrainingSession.id == session_id,
                TrainingSession.tenant_id == tenant_id,
                TrainingSession.student_id == student.id,
                TrainingSession.ended_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active training session not found")
    now = utc_now()
    elapsed = max(0, int((now - session.last_heartbeat_at).total_seconds()))
    # A heartbeat cannot credit more than 60 seconds, preventing a sleeping tab
    # or forged long pause from inflating regulatory study time.
    credited = min(elapsed, 60)
    session.active_seconds += credited
    session.last_heartbeat_at = now
    await db.commit()
    return SessionHeartbeatResponse(
        session_id=session.id,
        active_seconds=session.active_seconds,
        credited_seconds=credited,
        last_heartbeat_at=now,
    )


@router.post("/sessions/{session_id}/end")
async def end_training_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    user_id = UUID(current_user["user_id"])
    student = (
        await db.execute(select(Student).where(Student.tenant_id == tenant_id, Student.user_id == user_id))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    session = (
        await db.execute(
            select(TrainingSession).where(
                TrainingSession.id == session_id,
                TrainingSession.tenant_id == tenant_id,
                TrainingSession.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Training session not found")
    if session.ended_at is None:
        now = utc_now()
        elapsed = max(0, int((now - session.last_heartbeat_at).total_seconds()))
        session.active_seconds += min(elapsed, 60)
        session.last_heartbeat_at = now
        session.ended_at = now
        profile = await ComplianceService.get_profile(
            db, tenant_id=tenant_id, course_id=session.course_id
        )
        db.add(
            TrainingAccessEvent(
                tenant_id=tenant_id,
                enrollment_id=session.enrollment_id,
                student_id=session.student_id,
                course_id=session.course_id,
                event_type="SESSION_ENDED",
                event_data={"active_seconds": session.active_seconds},
                session_id=session.id,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                retain_until=ComplianceService.retention_until(profile=profile, occurred_at=now),
            )
        )
        await db.commit()
    return {"session_id": str(session.id), "active_seconds": session.active_seconds, "ended_at": session.ended_at}
