from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.normalization import validate_cpf
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.class_model import Class
from app.models.compliance import (
    ComplianceStatus,
    CourseComplianceProfile,
    CourseProfessionalAssignment,
    PedagogicalProjectStatus,
    PedagogicalProjectVersion,
    PracticalCompletionEvidence,
    TrainingAccessLog,
    TrainingProfessional,
)
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.schemas.compliance import (
    ComplianceApproveRequest,
    ComplianceProfileResponse,
    ComplianceProfileUpsert,
    ComplianceReadinessResponse,
    PedagogicalProjectCreate,
    PedagogicalProjectResponse,
    PracticalEvidenceCreate,
    ProfessionalAssignmentCreate,
    TrainingAccessLogResponse,
    TrainingProfessionalCreate,
    TrainingProfessionalResponse,
)
from app.services.compliance_service import ComplianceService

router = APIRouter()


async def _course(db: AsyncSession, tenant_id: UUID, course_id: UUID) -> Course:
    obj = (
        await db.execute(
            select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    return obj


@router.get("/professionals", response_model=list[TrainingProfessionalResponse])
async def list_professionals(
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
async def create_professional(
    payload: TrainingProfessionalCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    try:
        cpf = validate_cpf(payload.cpf)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    professional = TrainingProfessional(
        tenant_id=tenant_id,
        full_name=payload.full_name.strip(),
        cpf=cpf,
        qualification=payload.qualification.strip(),
        professional_council=payload.professional_council,
        registration_number=payload.registration_number,
        registration_state=payload.registration_state,
        is_active=payload.is_active,
        signature_method=payload.signature_method,
        signature_reference=payload.signature_reference,
        signature_verified_at=payload.signature_verified_at,
    )
    db.add(professional)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Profissional já cadastrado neste tenant") from exc
    await db.refresh(professional)
    return professional


@router.post(
    "/courses/{course_id}/pedagogical-projects",
    response_model=PedagogicalProjectResponse,
    status_code=201,
)
async def create_pedagogical_project(
    course_id: UUID,
    payload: PedagogicalProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == payload.technical_responsible_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not professional:
        raise HTTPException(status_code=422, detail="Responsável técnico inválido ou inativo")
    last_version = await db.scalar(
        select(func.coalesce(func.max(PedagogicalProjectVersion.version), 0)).where(
            PedagogicalProjectVersion.tenant_id == tenant_id,
            PedagogicalProjectVersion.course_id == course_id,
        )
    ) or 0
    project = PedagogicalProjectVersion(
        tenant_id=tenant_id,
        course_id=course_id,
        version=int(last_version) + 1,
        status=PedagogicalProjectStatus.DRAFT.value,
        **payload.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get(
    "/courses/{course_id}/pedagogical-projects",
    response_model=list[PedagogicalProjectResponse],
)
async def list_pedagogical_projects(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    return list(
        (
            await db.execute(
                select(PedagogicalProjectVersion)
                .where(
                    PedagogicalProjectVersion.tenant_id == tenant_id,
                    PedagogicalProjectVersion.course_id == course_id,
                )
                .order_by(PedagogicalProjectVersion.version.desc())
            )
        ).scalars().all()
    )


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
        raise HTTPException(status_code=404, detail="Projeto Pedagógico não encontrado")
    # NR-1 Annex II: project review at least every two years or on normative change.
    project.status = PedagogicalProjectStatus.APPROVED.value
    project.approved_at = utc_now()
    project.approved_by_user_id = UUID(current_user["user_id"])
    project.valid_until = (utc_now() + timedelta(days=730)).date()
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/courses/{course_id}/professionals", status_code=201)
async def assign_professional(
    course_id: UUID,
    payload: ProfessionalAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    project = (
        await db.execute(
            select(PedagogicalProjectVersion).where(
                PedagogicalProjectVersion.id == payload.pedagogical_project_version_id,
                PedagogicalProjectVersion.tenant_id == tenant_id,
                PedagogicalProjectVersion.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == payload.professional_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not project or not professional:
        raise HTTPException(status_code=422, detail="Projeto ou profissional inválido")
    if payload.role not in {"INSTRUCTOR", "TECHNICAL_RESPONSIBLE"}:
        raise HTTPException(status_code=422, detail="Função profissional inválida")
    assignment = CourseProfessionalAssignment(
        tenant_id=tenant_id,
        course_id=course_id,
        **payload.model_dump(),
    )
    db.add(assignment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Vínculo profissional já existe") from exc
    return {"id": str(assignment.id), "created": True}


@router.get("/courses/{course_id}/profile", response_model=ComplianceProfileResponse)
async def get_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil regulatório ainda não cadastrado")
    return profile


@router.put("/courses/{course_id}/profile", response_model=ComplianceProfileResponse)
async def upsert_profile(
    course_id: UUID,
    payload: ComplianceProfileUpsert,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not profile:
        profile = CourseComplianceProfile(tenant_id=tenant_id, course_id=course_id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    # Any factual/regulatory change invalidates the previous approval.
    profile.status = ComplianceStatus.IN_REVIEW.value
    profile.official_issuance_enabled = False
    profile.approved_at = None
    profile.approved_by_professional_id = None
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/courses/{course_id}/readiness", response_model=ComplianceReadinessResponse)
async def readiness(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    result = await ComplianceService.readiness(db, tenant_id=tenant_id, course_id=course_id)
    return ComplianceReadinessResponse(ready=result.ready, issues=result.issues)


@router.post("/courses/{course_id}/approve", response_model=ComplianceProfileResponse)
async def approve_profile(
    course_id: UUID,
    payload: ComplianceApproveRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    try:
        profile = await ComplianceService.approve_profile(
            db,
            tenant_id=tenant_id,
            course_id=course_id,
            approving_professional_id=payload.approving_professional_id,
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/courses/{course_id}/practical-evidence", status_code=201)
async def record_practical_evidence(
    course_id: UUID,
    payload: PracticalEvidenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    enrollment = (
        await db.execute(
            select(Enrollment, Student, Class)
            .join(Student, Enrollment.student_id == Student.id)
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.id == payload.enrollment_id,
                Enrollment.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
                Class.tenant_id == tenant_id,
                Class.course_id == course_id,
            )
        )
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Matrícula não encontrada para este curso")
    enrollment_obj, student, _class_obj = enrollment
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == payload.professional_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not professional:
        raise HTTPException(status_code=422, detail="Instrutor/responsável inválido")
    if payload.result not in {"SATISFATORIO", "INSATISFATORIO"}:
        raise HTTPException(status_code=422, detail="Resultado prático inválido")
    evidence = PracticalCompletionEvidence(
        tenant_id=tenant_id,
        enrollment_id=enrollment_obj.id,
        student_id=student.id,
        course_id=course_id,
        professional_id=payload.professional_id,
        occurred_on=payload.occurred_on,
        location=payload.location,
        result=payload.result,
        notes=payload.notes,
        recorded_by_user_id=UUID(current_user["user_id"]),
    )
    db.add(evidence)
    await db.commit()
    return {"id": str(evidence.id), "created": True}


@router.get("/courses/{course_id}/access-logs", response_model=list[TrainingAccessLogResponse])
async def list_access_logs(
    course_id: UUID,
    enrollment_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _course(db, tenant_id, course_id)
    stmt = select(TrainingAccessLog).where(
        TrainingAccessLog.tenant_id == tenant_id,
        TrainingAccessLog.course_id == course_id,
    )
    if enrollment_id:
        stmt = stmt.where(TrainingAccessLog.enrollment_id == enrollment_id)
    return list((await db.execute(stmt.order_by(TrainingAccessLog.occurred_at))).scalars().all())
