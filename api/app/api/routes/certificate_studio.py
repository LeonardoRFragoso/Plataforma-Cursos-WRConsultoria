from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.certificate_template import (
    CertificateTemplate,
    CertificateTemplateVersion,
    CertificateTemplateVersionStatus,
    CourseCertificateTemplateAssignment,
)
from app.schemas.certificate_studio import (
    CertificateStudioPreviewRequest,
    CertificateTemplateAssignmentRequest,
    CertificateTemplateAssignmentResponse,
    CertificateTemplateCreate,
    CertificateTemplateResponse,
    CertificateTemplateResolution,
    CertificateTemplateUpdate,
    CertificateTemplateVersionCreate,
    CertificateTemplateVersionResponse,
    CertificateTemplateVersionUpdate,
)
from app.services.certificate_studio_service import (
    CertificateStudioRenderer,
    CertificateStudioService,
)

router = APIRouter()


def _actor(current_user: dict) -> UUID:
    return UUID(current_user["user_id"])


async def _template(db: AsyncSession, tenant_id: UUID, template_id: UUID, *, lock: bool = False):
    stmt = select(CertificateTemplate).where(
        CertificateTemplate.id == template_id,
        CertificateTemplate.tenant_id == tenant_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Certificate template not found")
    return item


async def _version(db: AsyncSession, tenant_id: UUID, template_id: UUID, version_id: UUID, *, lock: bool = False):
    stmt = select(CertificateTemplateVersion).where(
        CertificateTemplateVersion.id == version_id,
        CertificateTemplateVersion.tenant_id == tenant_id,
        CertificateTemplateVersion.template_id == template_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Certificate template version not found")
    return item


@router.get("/templates", response_model=list[CertificateTemplateResponse])
async def list_templates(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(CertificateTemplate).where(CertificateTemplate.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(CertificateTemplate.is_active.is_(True))
    return list((await db.execute(stmt.order_by(CertificateTemplate.name.asc()))).scalars().all())


@router.post("/templates", response_model=CertificateTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: CertificateTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = CertificateTemplate(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        slug=payload.slug,
        is_active=True,
        created_by=_actor(current_user),
        updated_by=_actor(current_user),
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_certificate_template_tenant_slug" in str(exc.orig):
            raise HTTPException(status_code=409, detail="Certificate template slug already exists") from exc
        raise
    await db.refresh(item)
    return item


@router.patch("/templates/{template_id}", response_model=CertificateTemplateResponse)
async def update_template(
    template_id: UUID,
    payload: CertificateTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = await _template(db, tenant_id, template_id, lock=True)
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.is_active is not None:
        item.is_active = payload.is_active
    item.updated_by = _actor(current_user)
    item.updated_at = utc_now()
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/templates/{template_id}/versions", response_model=list[CertificateTemplateVersionResponse])
async def list_versions(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _template(db, tenant_id, template_id)
    return list(
        (
            await db.execute(
                select(CertificateTemplateVersion)
                .where(
                    CertificateTemplateVersion.tenant_id == tenant_id,
                    CertificateTemplateVersion.template_id == template_id,
                )
                .order_by(CertificateTemplateVersion.version.desc())
            )
        ).scalars().all()
    )


@router.post(
    "/templates/{template_id}/versions",
    response_model=CertificateTemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    template_id: UUID,
    payload: CertificateTemplateVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    try:
        item = await CertificateStudioService.create_version(
            db,
            tenant_id=tenant_id,
            template_id=template_id,
            actor_id=_actor(current_user),
            visual_config=payload.visual_config,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/templates/{template_id}/versions/{version_id}", response_model=CertificateTemplateVersionResponse)
async def update_version(
    template_id: UUID,
    version_id: UUID,
    payload: CertificateTemplateVersionUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = await _version(db, tenant_id, template_id, version_id, lock=True)
    if item.status != CertificateTemplateVersionStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Published certificate template versions are immutable")
    item.visual_config = payload.visual_config.model_dump(mode="json")
    item.updated_at = utc_now()
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/templates/{template_id}/versions/{version_id}/publish", response_model=CertificateTemplateVersionResponse)
async def publish_version(
    template_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    await _template(db, tenant_id, template_id)
    try:
        item = await CertificateStudioService.publish_version(
            db,
            tenant_id=tenant_id,
            template_id=template_id,
            version_id=version_id,
            actor_id=_actor(current_user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/preview")
async def preview_template(
    payload: CertificateStudioPreviewRequest,
    _current_user: dict = Depends(get_current_admin),
):
    pdf = CertificateStudioRenderer.preview(payload.visual_config)
    digest = hashlib.sha256(pdf).hexdigest()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=certificate-studio-preview.pdf",
            "X-Certificate-Studio-Preview": "NO-VALIDITY",
            "X-Certificate-SHA256": digest,
            "Cache-Control": "no-store",
        },
    )


@router.put("/courses/{course_id}/assignment", response_model=CertificateTemplateAssignmentResponse)
async def assign_template(
    course_id: UUID,
    payload: CertificateTemplateAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    try:
        item = await CertificateStudioService.assign_template(
            db,
            tenant_id=tenant_id,
            course_id=course_id,
            template_id=payload.template_id,
            actor_id=_actor(current_user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/courses/{course_id}/assignment", status_code=status.HTTP_204_NO_CONTENT)
async def reset_course_template(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    item = (
        await db.execute(
            select(CourseCertificateTemplateAssignment).where(
                CourseCertificateTemplateAssignment.tenant_id == tenant_id,
                CourseCertificateTemplateAssignment.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/courses/{course_id}/resolution", response_model=CertificateTemplateResolution)
async def get_course_resolution(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    resolution = await CertificateStudioService.resolve_for_course(
        db,
        tenant_id=tenant_id,
        course_id=course_id,
    )
    return CertificateTemplateResolution(
        source=resolution["source"],
        template_id=resolution["template_id"],
        template_version_id=resolution["template_version_id"],
        template_name=resolution["template_name"],
        version=resolution["version"],
        visual_config=resolution["visual_config"],
    )
