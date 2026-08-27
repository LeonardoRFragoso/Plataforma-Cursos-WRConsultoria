from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.certificate_signing import CertificateSigningJob, CertificateSigningProfile
from app.models.class_model import Class
from app.models.compliance import CourseComplianceProfile
from app.models.compliance_retention import (
    ComplianceRetentionPolicyVersion,
    RetentionPolicyStatus,
)
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.governance import AdminAuditLog
from app.models.tenant import Tenant
from app.models.training_evidence import EnrollmentComplianceProgress, TrainingAccessEvent
from app.schemas.compliance_operations import (
    ComplianceClassReport,
    ComplianceOperationsSummary,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)

router = APIRouter()


def _actor(current_user: dict) -> UUID:
    return UUID(current_user["user_id"])


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


async def _grouped_counts(db: AsyncSession, column, *criteria) -> dict[str, int]:
    rows = (
        await db.execute(
            select(column, func.count())
            .where(*criteria)
            .group_by(column)
        )
    ).all()
    return {str(key): int(count) for key, count in rows if key is not None}


async def _latest_approved_retention(
    db: AsyncSession,
    tenant_id: UUID,
) -> ComplianceRetentionPolicyVersion | None:
    return (
        await db.execute(
            select(ComplianceRetentionPolicyVersion)
            .where(
                ComplianceRetentionPolicyVersion.tenant_id == tenant_id,
                ComplianceRetentionPolicyVersion.status == RetentionPolicyStatus.APPROVED,
            )
            .order_by(ComplianceRetentionPolicyVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.get("/summary", response_model=ComplianceOperationsSummary)
async def compliance_operations_summary(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    now = utc_now()
    due_limit = now + timedelta(days=30)

    course_status_counts = await _grouped_counts(
        db,
        CourseComplianceProfile.status,
        CourseComplianceProfile.tenant_id == tenant_id,
    )
    enrollment_state_counts = await _grouped_counts(
        db,
        EnrollmentComplianceProgress.state,
        EnrollmentComplianceProgress.tenant_id == tenant_id,
    )
    signing_job_status_counts = await _grouped_counts(
        db,
        CertificateSigningJob.status,
        CertificateSigningJob.tenant_id == tenant_id,
    )

    reviews_expired = int(
        await db.scalar(
            select(func.count())
            .select_from(CourseComplianceProfile)
            .where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.next_compliance_review_at.is_not(None),
                CourseComplianceProfile.next_compliance_review_at <= now,
            )
        )
        or 0
    )
    reviews_due_30_days = int(
        await db.scalar(
            select(func.count())
            .select_from(CourseComplianceProfile)
            .where(
                CourseComplianceProfile.tenant_id == tenant_id,
                CourseComplianceProfile.next_compliance_review_at.is_not(None),
                CourseComplianceProfile.next_compliance_review_at > now,
                CourseComplianceProfile.next_compliance_review_at <= due_limit,
            )
        )
        or 0
    )

    signing_profile = (
        await db.execute(
            select(CertificateSigningProfile).where(
                CertificateSigningProfile.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    signer_not_after = signing_profile.certificate_not_after if signing_profile else None
    signer_expired = bool(signer_not_after and signer_not_after <= now)
    signer_due = bool(
        signer_not_after
        and now < signer_not_after <= due_limit
    )

    missing_ledger = int(
        await db.scalar(
            select(func.count())
            .select_from(EnrollmentComplianceProgress)
            .where(
                EnrollmentComplianceProgress.tenant_id == tenant_id,
                ~exists(
                    select(TrainingAccessEvent.id).where(
                        TrainingAccessEvent.tenant_id == tenant_id,
                        TrainingAccessEvent.enrollment_id
                        == EnrollmentComplianceProgress.enrollment_id,
                    )
                ),
            )
        )
        or 0
    )
    retention = await _latest_approved_retention(db, tenant_id)

    return ComplianceOperationsSummary(
        generated_at=now,
        course_status_counts=course_status_counts,
        enrollment_state_counts=enrollment_state_counts,
        signing_job_status_counts=signing_job_status_counts,
        reviews_expired=reviews_expired,
        reviews_due_30_days=reviews_due_30_days,
        signer_profile_enabled=bool(signing_profile and signing_profile.enabled),
        signer_certificate_expires_30_days=signer_due,
        signer_certificate_expired=signer_expired,
        signer_certificate_not_after=signer_not_after,
        enrollments_without_ledger_events=missing_ledger,
        approved_retention_policy_version=(retention.version if retention else None),
        retention_policy_ready=retention is not None,
    )


@router.get("/classes/{class_id}/report", response_model=ComplianceClassReport)
async def compliance_class_report(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    row = (
        await db.execute(
            select(Class, Course, CourseComplianceProfile)
            .join(Course, Class.course_id == Course.id)
            .outerjoin(
                CourseComplianceProfile,
                (CourseComplianceProfile.course_id == Course.id)
                & (CourseComplianceProfile.tenant_id == tenant_id),
            )
            .where(
                Class.id == class_id,
                Class.tenant_id == tenant_id,
                Course.tenant_id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Class not found")
    class_obj, course, profile = row
    if not profile:
        raise HTTPException(
            status_code=409,
            detail="Class course is not configured as regulatory training",
        )

    enrollment_count = int(
        await db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_id,
            )
        )
        or 0
    )
    state_rows = (
        await db.execute(
            select(EnrollmentComplianceProgress.state, func.count())
            .join(
                Enrollment,
                EnrollmentComplianceProgress.enrollment_id == Enrollment.id,
            )
            .where(
                EnrollmentComplianceProgress.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_id,
            )
            .group_by(EnrollmentComplianceProgress.state)
        )
    ).all()
    event_count = int(
        await db.scalar(
            select(func.count())
            .select_from(TrainingAccessEvent)
            .join(Enrollment, TrainingAccessEvent.enrollment_id == Enrollment.id)
            .where(
                TrainingAccessEvent.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_id,
            )
        )
        or 0
    )
    certificate_rows = (
        await db.execute(
            select(Certificate.status, func.count())
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .where(
                Certificate.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_id,
            )
            .group_by(Certificate.status)
        )
    ).all()
    signing_rows = (
        await db.execute(
            select(CertificateSigningJob.status, func.count())
            .join(Certificate, CertificateSigningJob.certificate_id == Certificate.id)
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .where(
                CertificateSigningJob.tenant_id == tenant_id,
                Certificate.tenant_id == tenant_id,
                Enrollment.tenant_id == tenant_id,
                Enrollment.class_id == class_id,
            )
            .group_by(CertificateSigningJob.status)
        )
    ).all()

    report = ComplianceClassReport(
        generated_at=utc_now(),
        class_id=class_obj.id,
        class_status=_enum_value(class_obj.status),
        course_id=course.id,
        course_code=course.code,
        course_name=course.name,
        regulatory_standard=profile.regulatory_standard,
        regulatory_version=profile.regulatory_version,
        start_date=class_obj.start_date.isoformat(),
        end_date=class_obj.end_date.isoformat(),
        pedagogical_project_version_id=class_obj.pedagogical_project_version_id,
        enrollment_count=enrollment_count,
        enrollment_state_counts={str(key): int(count) for key, count in state_rows},
        training_event_count=event_count,
        certificate_status_counts={str(key): int(count) for key, count in certificate_rows},
        signing_job_status_counts={str(key): int(count) for key, count in signing_rows},
    )
    db.add(
        AdminAuditLog(
            tenant_id=tenant_id,
            actor_id=_actor(current_user),
            actor_role=current_user.get("role", "admin"),
            method="GET",
            path=f"/api/v1/compliance/operations/classes/{class_id}/report",
            status_code=200,
        )
    )
    await db.commit()
    return report


@router.get(
    "/retention-policy/versions",
    response_model=list[RetentionPolicyResponse],
)
async def list_retention_policy_versions(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    return list(
        (
            await db.execute(
                select(ComplianceRetentionPolicyVersion)
                .where(ComplianceRetentionPolicyVersion.tenant_id == tenant_id)
                .order_by(ComplianceRetentionPolicyVersion.version.desc())
            )
        ).scalars().all()
    )


@router.post(
    "/retention-policy/versions",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_retention_policy_version(
    payload: RetentionPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    # Serialize version allocation per tenant by locking the tenant row. This
    # guarantees that even the FIRST version (which has no existing policy row
    # to SELECT ... FOR UPDATE) cannot be allocated twice concurrently: every
    # creator contends on the same tenant row before computing the next
    # version. The unique constraint remains the final race-safety boundary.
    await db.execute(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update()
    )
    latest = (
        await db.execute(
            select(ComplianceRetentionPolicyVersion)
            .where(ComplianceRetentionPolicyVersion.tenant_id == tenant_id)
            .order_by(ComplianceRetentionPolicyVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = (latest.version + 1 if latest else 1)
    item = ComplianceRetentionPolicyVersion(
        tenant_id=tenant_id,
        version=next_version,
        status=RetentionPolicyStatus.DRAFT,
        created_by=_actor(current_user),
        **payload.model_dump(),
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        # Defensive fallback for any residual race (e.g. a version inserted
        # by a path that bypassed the tenant lock). Re-read the latest
        # version once and retry; never surface a raw 500 to the caller.
        await db.rollback()
        await db.execute(
            select(Tenant).where(Tenant.id == tenant_id).with_for_update()
        )
        latest = (
            await db.execute(
                select(ComplianceRetentionPolicyVersion)
                .where(
                    ComplianceRetentionPolicyVersion.tenant_id == tenant_id
                )
                .order_by(ComplianceRetentionPolicyVersion.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        retry_version = (latest.version + 1 if latest else 1)
        item = ComplianceRetentionPolicyVersion(
            tenant_id=tenant_id,
            version=retry_version,
            status=RetentionPolicyStatus.DRAFT,
            created_by=_actor(current_user),
            **payload.model_dump(),
        )
        db.add(item)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Retention policy version could not be allocated; retry the request.",
            )
    await db.refresh(item)
    return item


@router.patch(
    "/retention-policy/versions/{version_id}",
    response_model=RetentionPolicyResponse,
)
async def update_retention_policy_version(
    version_id: UUID,
    payload: RetentionPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = (
        await db.execute(
            select(ComplianceRetentionPolicyVersion)
            .where(
                ComplianceRetentionPolicyVersion.id == version_id,
                ComplianceRetentionPolicyVersion.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Retention policy version not found")
    if item.status != RetentionPolicyStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Approved retention policy versions are immutable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = utc_now()
    await db.commit()
    await db.refresh(item)
    return item


@router.post(
    "/retention-policy/versions/{version_id}/approve",
    response_model=RetentionPolicyResponse,
)
async def approve_retention_policy_version(
    version_id: UUID,
    payload: RetentionPolicyUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = (
        await db.execute(
            select(ComplianceRetentionPolicyVersion)
            .where(
                ComplianceRetentionPolicyVersion.id == version_id,
                ComplianceRetentionPolicyVersion.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Retention policy version not found")
    if item.status == RetentionPolicyStatus.APPROVED:
        return item

    # Allow a single atomic approve-with-final-inputs call: if a body is
    # supplied, apply the final legal inputs to the DRAFT before validating
    # them. This mirrors the frontend's save-then-approve flow but makes
    # approval atomic and avoids a race where a draft is approved before its
    # final inputs are persisted.
    if payload is not None:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.updated_at = utc_now()

    required_periods = {
        "certificate_retention_days": item.certificate_retention_days,
        "assessment_retention_days": item.assessment_retention_days,
        "training_event_retention_days": item.training_event_retention_days,
        "student_confirmation_retention_days": item.student_confirmation_retention_days,
        "practical_evidence_retention_days": item.practical_evidence_retention_days,
    }
    missing = [key for key, value in required_periods.items() if not value]
    if not item.legal_basis:
        missing.append("legal_basis")
    if not item.purpose:
        missing.append("purpose")
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Retention policy requires explicit legal approval inputs",
                "missing": missing,
                "automatic_deletion_enabled": False,
            },
        )

    item.status = RetentionPolicyStatus.APPROVED
    item.approved_at = utc_now()
    item.approved_by = _actor(current_user)
    await db.commit()
    await db.refresh(item)
    return item
