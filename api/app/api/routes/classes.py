from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.compliance import (
    ComplianceStatus,
    CourseComplianceProfile,
    PedagogicalProjectStatus,
    PedagogicalProjectVersion,
    TrainingProfessional,
)
from app.models.course import Course, CourseModality
from app.models.user import User, UserRole
from app.schemas.class_schema import ClassCreate, ClassResponse, ClassUpdate
from app.services.assessment_service import course_requires_assessment

router = APIRouter()


def _generate_ead_access_link(course_id: UUID) -> str:
    """Generate the canonical platform EAD access URL for a course.

    Uses the configured FRONTEND_URL (the public web application base URL)
    + the authenticated learning route. This is the platform's own access
    point — NOT an external meeting link.
    """
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/courses/{course_id}/learn"


async def _validate_regulatory_class_opening(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    course: Course,
    profile: CourseComplianceProfile,
) -> UUID:
    """Revalidate critical compliance facts at the class-opening boundary.

    ``COMPLIANCE_READY`` is not treated as an eternal cache. If the responsible
    professional is later deactivated, the review date expires, the project is
    superseded, or course facts drift, a new class cannot silently reuse stale
    approval state.
    """
    if profile.status != ComplianceStatus.COMPLIANCE_READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory course must be compliance-ready before creating a class",
        )
    if profile.requires_practical_component:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Practical component tracking is required before opening this regulatory class",
        )
    if not profile.certificate_required_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory certificate fields are not configured",
        )
    if (
        profile.next_compliance_review_at is None
        or profile.next_compliance_review_at <= utc_now()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory compliance review is missing or expired",
        )
    if profile.requires_final_assessment:
        if profile.minimum_score is None or not course_requires_assessment(course.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Required final assessment is not consistently configured",
            )

    if not profile.technical_responsible_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technical responsible is not configured",
        )
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == profile.technical_responsible_id,
                TrainingProfessional.tenant_id == tenant_id,
                TrainingProfessional.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not professional:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technical responsible is missing or inactive",
        )

    if not profile.pedagogical_project_version_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compliance-ready course has no pedagogical project version",
        )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compliance-ready course does not reference an approved pedagogical project",
        )
    if abs(float(project.workload_hours) - float(course.carga_horaria)) >= 0.01:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pedagogical project workload no longer matches the course",
        )
    if project.delivery_mode != course.modality.value or profile.delivery_mode != course.modality.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory delivery mode no longer matches the course modality",
        )
    return project.id


@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = await db.get(Course, class_data.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    if not course.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course must be active to create a class",
        )

    compliance_profile = (
        await db.execute(
            select(CourseComplianceProfile).where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.course_id == course.id,
            )
        )
    ).scalar_one_or_none()
    pinned_project_id = None
    if compliance_profile:
        pinned_project_id = await _validate_regulatory_class_opening(
            db,
            tenant_id=tenant_id,
            course=course,
            profile=compliance_profile,
        )

    responsible = await db.get(User, class_data.responsible_admin_id)
    if not responsible or not responsible.is_active or responsible.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Responsible user must be an active admin",
        )

    if class_data.start_date >= class_data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )

    if class_data.max_students <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_students must be greater than zero",
        )

    if class_data.status == ClassStatus.CANCELADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a class with CANCELADA status",
        )

    ead_link = class_data.ead_link
    if course.modality in (CourseModality.EAD, CourseModality.SEMIPRESENCIAL) and not ead_link:
        ead_link = _generate_ead_access_link(course.id)

    if course.modality == CourseModality.PRESENCIAL and not class_data.location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="In-person classes require a location",
        )

    if course.modality == CourseModality.SEMIPRESENCIAL and not (class_data.location or ead_link):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hybrid classes require a location or ead_link",
        )

    class_dict = class_data.model_dump()
    class_dict["ead_link"] = ead_link
    class_dict["pedagogical_project_version_id"] = pinned_project_id
    class_obj = Class(**class_dict)
    db.add(class_obj)
    await db.commit()
    await db.refresh(class_obj)
    return class_obj


@router.get("/", response_model=list[ClassResponse])
async def list_classes(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Class).offset(skip).limit(limit)
    result = await db.execute(stmt)
    classes = result.scalars().all()
    return classes


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(class_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()

    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    return class_obj


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: UUID,
    class_data: ClassUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()

    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    update_data = class_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(class_obj, field, value)

    await db.commit()
    await db.refresh(class_obj)
    return class_obj


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Class).where(Class.id == class_id)
    result = await db.execute(stmt)
    class_obj = result.scalar_one_or_none()

    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    await db.delete(class_obj)
    await db.commit()
