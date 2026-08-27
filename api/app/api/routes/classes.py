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
    """Generate the canonical platform EAD access URL for a course."""
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/courses/{course_id}/learn"


async def _validate_regulatory_class_opening(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    course: Course,
    profile: CourseComplianceProfile,
) -> UUID:
    """Revalidate mutable compliance facts before opening a regulated class."""
    if profile.status != ComplianceStatus.COMPLIANCE_READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory course must be compliance-ready before creating a class",
        )
    if profile.last_compliance_review_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compliance-ready course has no completed compliance review",
        )
    if profile.next_compliance_review_at is None or profile.next_compliance_review_at <= utc_now():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course compliance review is missing or expired",
        )
    if course.updated_at and course.updated_at > profile.last_compliance_review_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course changed after the last compliance review",
        )
    if profile.delivery_mode != course.modality.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compliance delivery mode no longer matches the course modality",
        )
    # Practical requirements are now supported by the training-evidence
    # runtime. The class may open, but the enrollment state machine will keep
    # certification blocked until a current SATISFACTORY practical record is
    # present for the enrollment.
    if profile.requires_final_assessment and not course_requires_assessment(course.code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Required final assessment is not configured for this course",
        )

    if not profile.technical_responsible_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compliance-ready course has no technical responsible",
        )
    professional = (
        await db.execute(
            select(TrainingProfessional).where(
                TrainingProfessional.id == profile.technical_responsible_id,
                TrainingProfessional.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not professional or not professional.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technical responsible is missing or inactive",
        )
    if professional.updated_at and professional.updated_at > profile.last_compliance_review_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technical responsible changed after the last compliance review",
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
            detail="Pedagogical project workload no longer matches the course workload",
        )
    if project.delivery_mode != course.modality.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pedagogical project delivery mode no longer matches the course modality",
        )
    return project.id


@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    course = (
        await db.execute(
            select(Course).where(Course.id == class_data.course_id, Course.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if not course.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course must be active to create a class")

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

    responsible = (
        await db.execute(
            select(User).where(
                User.id == class_data.responsible_admin_id,
                User.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not responsible or not responsible.is_active or responsible.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Responsible user must be an active admin")
    if class_data.start_date >= class_data.end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    if class_data.max_students <= 0:
        raise HTTPException(status_code=400, detail="max_students must be greater than zero")
    if class_data.status == ClassStatus.CANCELADA:
        raise HTTPException(status_code=400, detail="Cannot create a class with CANCELADA status")

    ead_link = class_data.ead_link
    if course.modality in (CourseModality.EAD, CourseModality.SEMIPRESENCIAL) and not ead_link:
        ead_link = _generate_ead_access_link(course.id)
    if course.modality == CourseModality.PRESENCIAL and not class_data.location:
        raise HTTPException(status_code=400, detail="In-person classes require a location")
    if course.modality == CourseModality.SEMIPRESENCIAL and not (class_data.location or ead_link):
        raise HTTPException(status_code=400, detail="Hybrid classes require a location or ead_link")

    class_dict = class_data.model_dump()
    class_dict["ead_link"] = ead_link
    class_dict["tenant_id"] = tenant_id
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
    tenant_id = get_current_tenant_id()
    stmt = select(Class).where(Class.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(class_id: UUID, db: AsyncSession = Depends(get_db)):
    tenant_id = get_current_tenant_id()
    class_obj = (
        await db.execute(select(Class).where(Class.id == class_id, Class.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_obj


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: UUID,
    class_data: ClassUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    class_obj = (
        await db.execute(select(Class).where(Class.id == class_id, Class.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
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
    tenant_id = get_current_tenant_id()
    class_obj = (
        await db.execute(select(Class).where(Class.id == class_id, Class.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    await db.delete(class_obj)
    await db.commit()
