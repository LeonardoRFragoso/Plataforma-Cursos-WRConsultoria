from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.normalization import validate_cpf
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.compliance import (
    ComplianceStatus,
    CourseComplianceProfile,
    CourseTrainingProfessional,
    PedagogicalProjectStatus,
    PedagogicalProjectVersion,
    ProfessionalAssignmentRole,
    TrainingProfessional,
)
from app.models.course import Course, CourseModality
from app.schemas.compliance import (
    ComplianceProfileResponse,
    ComplianceProfileUpsert,
    ComplianceReadinessResponse,
    CourseProfessionalAssignmentCreate,
    CourseProfessionalAssignmentResponse,
    PedagogicalProjectApproval,
    PedagogicalProjectCreate,
    PedagogicalProjectResponse,
    PedagogicalProjectUpdate,
    TrainingProfessionalCreate,
    TrainingProfessionalResponse,
    TrainingProfessionalUpdate,
)

router = APIRouter()
_DELIVERY_MODES = frozenset(item.value for item in CourseModality)
_ASSIGNMENT_ROLES = frozenset(
    {
        ProfessionalAssignmentRole.INSTRUCTOR,
        ProfessionalAssignmentRole.TECHNICAL_RESPONSIBLE,
    }
)
_EDITABLE_PROJECT_STATUSES = frozenset(
    {PedagogicalProjectStatus.DRAFT, PedagogicalProjectStatus.IN_REVIEW}
)


def _clean_required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field} cannot be empty")
    return cleaned


def _normalize_delivery_mode(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _DELIVERY_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid delivery mode. Allowed: {', '.join(sorted(_DELIVERY_MODES))}",
        )
    return normalized


async def _load_course(
    db: AsyncSession,
    tenant_id: UUID,
    course_id: UUID,
    *,
    for_update: bool = False,
) -> Course:
    stmt = select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    course = (await db.execute(stmt)).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


async def _load_professional(
    db: AsyncSession,
    tenant_id: UUID,
    professional_id: UUID,
) -> TrainingProfessional:
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == professional_id,
                TrainingProfessional.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not professional:
        raise HTTPException(status_code=404, detail="Training professional not found")
    return professional


async def _load_project(
    db: AsyncSession,
    tenant_id: UUID,
    course_id: UUID,
    project_id: UUID,
) -> PedagogicalProjectVersion:
    project = (
        await db.execute(
            select(PedagogicalProjectVersion).where(
                PedagogicalProjectVersion.id == project_id,
                PedagogicalProjectVersion.tenant_id == tenant_id,
                PedagogicalProjectVersion.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Pedagogical project version not found")
    return project


async def _load_profile(
    db: AsyncSession,
    tenant_id: UUID,
    course_id: UUID,
) -> CourseComplianceProfile:
    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Course compliance profile not found")
    return profile


@router.post(
    "/professionals",
    response_model=TrainingProfessionalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_training_professional(
    payload: TrainingProfessionalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    try:
        cpf = validate_cpf(payload.cpf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = (
        await db.execute(
            select(TrainingProfessional.id).where(
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.cpf == cpf,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Training professional with this CPF already exists")

    professional = TrainingProfessional(
        tenant_id=tenant_id,
        full_name=_clean_required(payload.full_name, "full_name"),
        cpf=cpf,
        qualification=_clean_required(payload.qualification, "qualification"),
        professional_registration=(
            payload.professional_registration.strip() if payload.professional_registration else None
        ),
        council=payload.council.strip().upper() if payload.council else None,
        registration_state=(
            payload.registration_state.strip().upper() if payload.registration_state else None
        ),
        is_active=True,
    )
    db.add(professional)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_training_professional_tenant_cpf" in str(exc.orig):
            raise HTTPException(
                status_code=409,
                detail="Training professional with this CPF already exists",
            ) from exc
        raise
    await db.refresh(professional)
    return professional


@router.get("/professionals", response_model=list[TrainingProfessionalResponse])
async def list_training_professionals(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TrainingProfessional).where(TrainingProfessional.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(TrainingProfessional.is_active.is_(True))
    return (
        await db.execute(stmt.order_by(TrainingProfessional.full_name.asc()))
    ).scalars().all()


@router.patch(
    "/professionals/{professional_id}",
    response_model=TrainingProfessionalResponse,
)
async def update_training_professional(
    professional_id: UUID,
    payload: TrainingProfessionalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    professional = await _load_professional(db, tenant_id, professional_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("full_name", "qualification"):
        if field in changes and changes[field] is not None:
            changes[field] = _clean_required(changes[field], field)
    for field in ("professional_registration", "council", "registration_state"):
        if field in changes and isinstance(changes[field], str):
            cleaned = changes[field].strip()
            if field in {"council", "registration_state"}:
                cleaned = cleaned.upper()
            changes[field] = cleaned or None
    for field, value in changes.items():
        setattr(professional, field, value)
    await db.commit()
    await db.refresh(professional)
    return professional


@router.post(
    "/courses/{course_id}/projects",
    response_model=PedagogicalProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pedagogical_project(
    course_id: UUID,
    payload: PedagogicalProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _load_course(db, tenant_id, course_id, for_update=True)
    delivery_mode = _normalize_delivery_mode(payload.delivery_mode)
    if delivery_mode != course.modality.value:
        raise HTTPException(
            status_code=409,
            detail="Pedagogical project delivery mode must match the course modality",
        )

    current_max = await db.scalar(
        select(func.coalesce(func.max(PedagogicalProjectVersion.version), 0)).where(
            PedagogicalProjectVersion.tenant_id == tenant_id,
            PedagogicalProjectVersion.course_id == course_id,
        )
    )
    project = PedagogicalProjectVersion(
        tenant_id=tenant_id,
        course_id=course_id,
        version=int(current_max or 0) + 1,
        status=PedagogicalProjectStatus.DRAFT,
        general_objective=_clean_required(payload.general_objective, "general_objective"),
        specific_objectives=payload.specific_objectives,
        target_audience=_clean_required(payload.target_audience, "target_audience"),
        teaching_strategy=_clean_required(payload.teaching_strategy, "teaching_strategy"),
        syllabus=payload.syllabus,
        workload_hours=payload.workload_hours,
        delivery_mode=delivery_mode,
        materials=payload.materials,
        assessment_methodology=_clean_required(
            payload.assessment_methodology,
            "assessment_methodology",
        ),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get(
    "/courses/{course_id}/projects",
    response_model=list[PedagogicalProjectResponse],
)
async def list_pedagogical_projects(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course(db, tenant_id, course_id)
    return (
        await db.execute(
            select(PedagogicalProjectVersion)
            .where(
                PedagogicalProjectVersion.tenant_id == tenant_id,
                PedagogicalProjectVersion.course_id == course_id,
            )
            .order_by(PedagogicalProjectVersion.version.desc())
        )
    ).scalars().all()


@router.patch(
    "/courses/{course_id}/projects/{project_id}",
    response_model=PedagogicalProjectResponse,
)
async def update_pedagogical_project(
    course_id: UUID,
    project_id: UUID,
    payload: PedagogicalProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _load_course(db, tenant_id, course_id)
    project = await _load_project(db, tenant_id, course_id, project_id)
    if project.status not in _EDITABLE_PROJECT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Approved or archived pedagogical project versions are immutable",
        )

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        requested_status = changes["status"].strip().upper()
        if requested_status not in _EDITABLE_PROJECT_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Project status can only move between DRAFT and IN_REVIEW before approval",
            )
        changes["status"] = requested_status
    if "delivery_mode" in changes and changes["delivery_mode"] is not None:
        mode = _normalize_delivery_mode(changes["delivery_mode"])
        if mode != course.modality.value:
            raise HTTPException(
                status_code=409,
                detail="Pedagogical project delivery mode must match the course modality",
            )
        changes["delivery_mode"] = mode
    for field in (
        "general_objective",
        "target_audience",
        "teaching_strategy",
        "assessment_methodology",
    ):
        if field in changes and changes[field] is not None:
            changes[field] = _clean_required(changes[field], field)
    for field, value in changes.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.post(
    "/courses/{course_id}/projects/{project_id}/approve",
    response_model=PedagogicalProjectResponse,
)
async def approve_pedagogical_project(
    course_id: UUID,
    project_id: UUID,
    payload: PedagogicalProjectApproval,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course(db, tenant_id, course_id, for_update=True)
    project = await _load_project(db, tenant_id, course_id, project_id)
    if project.status == PedagogicalProjectStatus.APPROVED:
        return project
    if project.status == PedagogicalProjectStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived project version cannot be approved")

    previous = (
        await db.execute(
            select(PedagogicalProjectVersion).where(
                PedagogicalProjectVersion.tenant_id == tenant_id,
                PedagogicalProjectVersion.course_id == course_id,
                PedagogicalProjectVersion.status == PedagogicalProjectStatus.APPROVED,
                PedagogicalProjectVersion.id != project.id,
            )
        )
    ).scalars().all()
    for item in previous:
        item.status = PedagogicalProjectStatus.ARCHIVED

    project.status = PedagogicalProjectStatus.APPROVED
    project.approved_at = utc_now()
    project.approved_by = UUID(current_user["user_id"])
    project.approval_notes = payload.approval_notes.strip() if payload.approval_notes else None

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if (
        profile
        and profile.status == ComplianceStatus.COMPLIANCE_READY
        and profile.pedagogical_project_version_id != project.id
    ):
        profile.status = ComplianceStatus.REVIEW_REQUIRED

    await db.commit()
    await db.refresh(project)
    return project


@router.get(
    "/courses/{course_id}/profile",
    response_model=ComplianceProfileResponse,
)
async def get_compliance_profile(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course(db, tenant_id, course_id)
    return await _load_profile(db, tenant_id, course_id)


@router.put(
    "/courses/{course_id}/profile",
    response_model=ComplianceProfileResponse,
)
async def upsert_compliance_profile(
    course_id: UUID,
    payload: ComplianceProfileUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _load_course(db, tenant_id, course_id)
    delivery_mode = _normalize_delivery_mode(payload.delivery_mode)
    if delivery_mode != course.modality.value:
        raise HTTPException(
            status_code=409,
            detail="Compliance delivery mode must match the course modality",
        )
    if payload.requires_final_assessment and payload.minimum_score is None:
        raise HTTPException(
            status_code=400,
            detail="minimum_score is required when final assessment is required",
        )

    if payload.technical_responsible_id:
        await _load_professional(db, tenant_id, payload.technical_responsible_id)
    if payload.pedagogical_project_version_id:
        await _load_project(
            db,
            tenant_id,
            course_id,
            payload.pedagogical_project_version_id,
        )

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    was_ready = bool(profile and profile.status == ComplianceStatus.COMPLIANCE_READY)
    values = payload.model_dump()
    values["regulatory_standard"] = _clean_required(
        payload.regulatory_standard,
        "regulatory_standard",
    ).upper()
    values["regulatory_version"] = _clean_required(
        payload.regulatory_version,
        "regulatory_version",
    )
    values["delivery_mode"] = delivery_mode
    values["prerequisites"] = payload.prerequisites.strip() if payload.prerequisites else None
    values["certificate_required_fields"] = [
        item.strip() for item in payload.certificate_required_fields if item.strip()
    ]

    if profile is None:
        profile = CourseComplianceProfile(
            tenant_id=tenant_id,
            course_id=course_id,
            status=ComplianceStatus.DRAFT,
            **values,
        )
        db.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)
        if was_ready:
            profile.status = ComplianceStatus.REVIEW_REQUIRED

    if payload.technical_responsible_id:
        assignment = (
            await db.execute(
                select(CourseTrainingProfessional).where(
                    CourseTrainingProfessional.tenant_id == tenant_id,
                    CourseTrainingProfessional.course_id == course_id,
                    CourseTrainingProfessional.professional_id == payload.technical_responsible_id,
                    CourseTrainingProfessional.role == ProfessionalAssignmentRole.TECHNICAL_RESPONSIBLE,
                )
            )
        ).scalar_one_or_none()
        if not assignment:
            db.add(
                CourseTrainingProfessional(
                    tenant_id=tenant_id,
                    course_id=course_id,
                    professional_id=payload.technical_responsible_id,
                    role=ProfessionalAssignmentRole.TECHNICAL_RESPONSIBLE,
                )
            )

    await db.commit()
    await db.refresh(profile)
    return profile


async def _readiness_blockers(
    db: AsyncSession,
    tenant_id: UUID,
    course: Course,
    profile: CourseComplianceProfile,
) -> list[str]:
    blockers: list[str] = []
    if profile.delivery_mode != course.modality.value:
        blockers.append("Compliance delivery mode does not match the course modality")
    if profile.requires_final_assessment and profile.minimum_score is None:
        blockers.append("Final assessment requires a configured minimum score")
    if not profile.certificate_required_fields:
        blockers.append("Certificate required fields have not been defined")
    if profile.next_compliance_review_at is None:
        blockers.append("Next compliance review date has not been defined")
    if profile.requires_practical_component:
        blockers.append("Practical component tracking must be implemented before this course can be marked ready")

    if profile.technical_responsible_id is None:
        blockers.append("Technical responsible has not been assigned")
    else:
        professional = (
            await db.execute(
                select(TrainingProfessional).where(
                    TrainingProfessional.id == profile.technical_responsible_id,
                    TrainingProfessional.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not professional or not professional.is_active:
            blockers.append("Technical responsible is missing or inactive")

    if profile.pedagogical_project_version_id is None:
        blockers.append("Approved pedagogical project version has not been selected")
    else:
        project = (
            await db.execute(
                select(PedagogicalProjectVersion).where(
                    PedagogicalProjectVersion.id == profile.pedagogical_project_version_id,
                    PedagogicalProjectVersion.tenant_id == tenant_id,
                    PedagogicalProjectVersion.course_id == course.id,
                )
            )
        ).scalar_one_or_none()
        if not project or project.status != PedagogicalProjectStatus.APPROVED:
            blockers.append("Selected pedagogical project is not approved")
        elif abs(float(project.workload_hours) - float(course.carga_horaria)) >= 0.01:
            blockers.append("Pedagogical project workload does not match the course workload")
        elif project.delivery_mode != course.modality.value:
            blockers.append("Pedagogical project delivery mode does not match the course modality")

    return blockers


@router.get(
    "/courses/{course_id}/readiness",
    response_model=ComplianceReadinessResponse,
)
async def compliance_readiness(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _load_course(db, tenant_id, course_id)
    profile = await _load_profile(db, tenant_id, course_id)
    blockers = await _readiness_blockers(db, tenant_id, course, profile)
    return ComplianceReadinessResponse(
        ready=not blockers and profile.status == ComplianceStatus.COMPLIANCE_READY,
        status=profile.status,
        blockers=blockers,
        profile=ComplianceProfileResponse.model_validate(profile),
    )


@router.post(
    "/courses/{course_id}/mark-ready",
    response_model=ComplianceReadinessResponse,
)
async def mark_compliance_ready(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await _load_course(db, tenant_id, course_id, for_update=True)
    profile = await _load_profile(db, tenant_id, course_id)
    blockers = await _readiness_blockers(db, tenant_id, course, profile)
    if blockers:
        profile.status = ComplianceStatus.REVIEW_REQUIRED
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Course is not compliance-ready",
                "blockers": blockers,
            },
        )

    profile.status = ComplianceStatus.COMPLIANCE_READY
    profile.last_compliance_review_at = utc_now()
    await db.commit()
    await db.refresh(profile)
    return ComplianceReadinessResponse(
        ready=True,
        status=profile.status,
        blockers=[],
        profile=ComplianceProfileResponse.model_validate(profile),
    )


@router.post(
    "/courses/{course_id}/professionals",
    response_model=CourseProfessionalAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_course_professional(
    course_id: UUID,
    payload: CourseProfessionalAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course(db, tenant_id, course_id)
    professional = await _load_professional(db, tenant_id, payload.professional_id)
    if not professional.is_active:
        raise HTTPException(status_code=409, detail="Inactive professional cannot be assigned")
    role = payload.role.strip().upper()
    if role not in _ASSIGNMENT_ROLES:
        raise HTTPException(status_code=400, detail="Invalid professional assignment role")

    existing = (
        await db.execute(
            select(CourseTrainingProfessional).where(
                CourseTrainingProfessional.tenant_id == tenant_id,
                CourseTrainingProfessional.course_id == course_id,
                CourseTrainingProfessional.professional_id == professional.id,
                CourseTrainingProfessional.role == role,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    assignment = CourseTrainingProfessional(
        tenant_id=tenant_id,
        course_id=course_id,
        professional_id=professional.id,
        role=role,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.get(
    "/courses/{course_id}/professionals",
    response_model=list[CourseProfessionalAssignmentResponse],
)
async def list_course_professionals(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _load_course(db, tenant_id, course_id)
    return (
        await db.execute(
            select(CourseTrainingProfessional)
            .where(
                CourseTrainingProfessional.tenant_id == tenant_id,
                CourseTrainingProfessional.course_id == course_id,
            )
            .order_by(CourseTrainingProfessional.created_at.asc())
        )
    ).scalars().all()


@router.delete(
    "/courses/{course_id}/professionals/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_course_professional(
    course_id: UUID,
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    assignment = (
        await db.execute(
            select(CourseTrainingProfessional).where(
                CourseTrainingProfessional.id == assignment_id,
                CourseTrainingProfessional.tenant_id == tenant_id,
                CourseTrainingProfessional.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Professional assignment not found")

    profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if (
        profile
        and profile.technical_responsible_id == assignment.professional_id
        and assignment.role == ProfessionalAssignmentRole.TECHNICAL_RESPONSIBLE
    ):
        raise HTTPException(
            status_code=409,
            detail="Technical responsible assignment is referenced by the compliance profile",
        )

    await db.delete(assignment)
    await db.commit()
