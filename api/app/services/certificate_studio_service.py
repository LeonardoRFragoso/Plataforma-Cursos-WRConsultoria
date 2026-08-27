from __future__ import annotations

import base64
import hashlib
import io
import uuid
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.certificate_template import (
    CertificateTemplate,
    CertificateTemplateVersion,
    CertificateTemplateVersionStatus,
    CourseCertificateTemplateAssignment,
)
from app.models.course import Course
from app.schemas.certificate_studio import CertificateVisualConfig
from app.services.certificate_document_service import CertificateDocumentService

SYSTEM_DEFAULT_CONFIG = CertificateVisualConfig()


def _config_dict(value: CertificateVisualConfig | dict | None) -> dict:
    if isinstance(value, CertificateVisualConfig):
        return value.model_dump(mode="json")
    return CertificateVisualConfig.model_validate(value or {}).model_dump(mode="json")


def visual_config_hash(value: CertificateVisualConfig | dict | None) -> str:
    import json

    payload = json.dumps(_config_dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hex(value: str):
    return colors.HexColor(value)


def _font_names(family: str) -> tuple[str, str]:
    if family == "TIMES":
        return "Times-Roman", "Times-Bold"
    if family == "COURIER":
        return "Courier", "Courier-Bold"
    return "Helvetica", "Helvetica-Bold"


def _image_from_data_uri(value: str | None, *, width: float, height: float) -> Image | None:
    if not value:
        return None
    try:
        _header, encoded = value.split(",", 1)
        data = base64.b64decode(encoded, validate=True)
        reader = ImageReader(io.BytesIO(data))
        img_w, img_h = reader.getSize()
        scale = min(width / img_w, height / img_h)
        return Image(io.BytesIO(data), width=img_w * scale, height=img_h * scale)
    except Exception as exc:  # schema already validates the payload; fail closed at rendering.
        raise ValueError("Certificate Studio logo could not be rendered") from exc


class CertificateStudioService:
    @staticmethod
    async def resolve_for_course(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> dict:
        assignment = (
            await db.execute(
                select(CourseCertificateTemplateAssignment, CertificateTemplate)
                .join(CertificateTemplate, CourseCertificateTemplateAssignment.template_id == CertificateTemplate.id)
                .where(
                    CourseCertificateTemplateAssignment.tenant_id == tenant_id,
                    CourseCertificateTemplateAssignment.course_id == course_id,
                    CertificateTemplate.tenant_id == tenant_id,
                    CertificateTemplate.is_active.is_(True),
                )
            )
        ).first()
        if assignment:
            link, template = assignment
            version = (
                await db.execute(
                    select(CertificateTemplateVersion)
                    .where(
                        CertificateTemplateVersion.tenant_id == tenant_id,
                        CertificateTemplateVersion.template_id == template.id,
                        CertificateTemplateVersion.status == CertificateTemplateVersionStatus.PUBLISHED,
                    )
                    .order_by(CertificateTemplateVersion.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if version:
                config = _config_dict(version.visual_config)
                return {
                    "source": "TENANT",
                    "template_id": str(template.id),
                    "template_version_id": str(version.id),
                    "template_name": template.name,
                    "template_slug": template.slug,
                    "version": version.version,
                    "visual_config": config,
                    "visual_config_sha256": visual_config_hash(config),
                    "resolved_at": utc_now().isoformat(),
                }

        config = SYSTEM_DEFAULT_CONFIG.model_dump(mode="json")
        return {
            "source": "SYSTEM",
            "template_id": None,
            "template_version_id": None,
            "template_name": "System Default",
            "template_slug": "system-default",
            "version": 1,
            "visual_config": config,
            "visual_config_sha256": visual_config_hash(config),
            "resolved_at": utc_now().isoformat(),
        }

    @staticmethod
    async def create_version(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        actor_id: uuid.UUID,
        visual_config: CertificateVisualConfig | dict | None,
    ) -> CertificateTemplateVersion:
        template = (
            await db.execute(
                select(CertificateTemplate)
                .where(CertificateTemplate.id == template_id, CertificateTemplate.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not template:
            raise LookupError("Certificate template not found")
        if not template.is_active:
            raise ValueError("Archived certificate template cannot receive a new version")
        max_version = await db.scalar(
            select(func.coalesce(func.max(CertificateTemplateVersion.version), 0)).where(
                CertificateTemplateVersion.tenant_id == tenant_id,
                CertificateTemplateVersion.template_id == template.id,
            )
        )
        item = CertificateTemplateVersion(
            tenant_id=tenant_id,
            template_id=template.id,
            version=int(max_version or 0) + 1,
            status=CertificateTemplateVersionStatus.DRAFT,
            visual_config=_config_dict(visual_config),
            created_by=actor_id,
        )
        db.add(item)
        await db.flush()
        return item

    @staticmethod
    async def publish_version(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        version_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> CertificateTemplateVersion:
        item = (
            await db.execute(
                select(CertificateTemplateVersion)
                .where(
                    CertificateTemplateVersion.id == version_id,
                    CertificateTemplateVersion.tenant_id == tenant_id,
                    CertificateTemplateVersion.template_id == template_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not item:
            raise LookupError("Certificate template version not found")
        if item.status == CertificateTemplateVersionStatus.PUBLISHED:
            return item
        CertificateVisualConfig.model_validate(item.visual_config or {})
        item.status = CertificateTemplateVersionStatus.PUBLISHED
        item.published_at = utc_now()
        item.published_by = actor_id
        await db.flush()
        return item

    @staticmethod
    async def assign_template(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
        template_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> CourseCertificateTemplateAssignment:
        course = (
            await db.execute(select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not course:
            raise LookupError("Course not found")
        template = (
            await db.execute(
                select(CertificateTemplate).where(
                    CertificateTemplate.id == template_id,
                    CertificateTemplate.tenant_id == tenant_id,
                    CertificateTemplate.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not template:
            raise LookupError("Active certificate template not found")
        published = await db.scalar(
            select(CertificateTemplateVersion.id)
            .where(
                CertificateTemplateVersion.tenant_id == tenant_id,
                CertificateTemplateVersion.template_id == template_id,
                CertificateTemplateVersion.status == CertificateTemplateVersionStatus.PUBLISHED,
            )
            .limit(1)
        )
        if not published:
            raise ValueError("Template must have a published version before assignment")
        assignment = (
            await db.execute(
                select(CourseCertificateTemplateAssignment)
                .where(
                    CourseCertificateTemplateAssignment.tenant_id == tenant_id,
                    CourseCertificateTemplateAssignment.course_id == course_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if assignment is None:
            assignment = CourseCertificateTemplateAssignment(
                tenant_id=tenant_id,
                course_id=course_id,
                template_id=template_id,
                assigned_by=actor_id,
                assigned_at=utc_now(),
            )
            db.add(assignment)
        else:
            assignment.template_id = template_id
            assignment.assigned_by = actor_id
            assignment.assigned_at = utc_now()
        await db.flush()
        return assignment


class CertificateStudioRenderer:
    @staticmethod
    def _page_decorator(canvas, doc, config: CertificateVisualConfig, *, preview: bool = False):
        width, height = A4
        canvas.saveState()
        background = config.background_color if config.background_style == "WHITE" else config.accent_color
        canvas.setFillColor(_hex(background))
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        if config.border_style != "NONE":
            canvas.setStrokeColor(_hex(config.primary_color))
            canvas.setLineWidth(1.2)
            canvas.rect(8 * mm, 8 * mm, width - 16 * mm, height - 16 * mm, stroke=1, fill=0)
            if config.border_style == "DOUBLE":
                canvas.setLineWidth(0.5)
                canvas.rect(11 * mm, 11 * mm, width - 22 * mm, height - 22 * mm, stroke=1, fill=0)
        if preview:
            canvas.setFillColor(colors.Color(0.7, 0.7, 0.7, alpha=0.22))
            canvas.setFont("Helvetica-Bold", 34)
            canvas.translate(width / 2, height / 2)
            canvas.rotate(34)
            canvas.drawCentredString(0, 0, "PRÉVIA — SEM VALIDADE")
        canvas.restoreState()

    @classmethod
    def render(cls, snapshot: dict, *, snapshot_sha256: str, preview: bool = False) -> bytes:
        visual = (snapshot.get("certificate_template") or {}).get("visual_config") or {}
        config = CertificateVisualConfig.model_validate(visual)
        regular_font, bold_font = _font_names(config.font_family)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=("Certificate Studio Preview" if preview else f"Certificate {snapshot['certificate']['number']}"),
            author=snapshot["issuer"]["name"],
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "StudioTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName=bold_font,
            textColor=_hex(config.primary_color),
            fontSize=(23 if config.preset == "MODERN" else 20),
            leading=27,
            spaceAfter=7 * mm,
        )
        centered = ParagraphStyle(
            "StudioCentered",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontName=regular_font,
            textColor=_hex(config.secondary_color),
            fontSize=11,
            leading=16,
        )
        body = ParagraphStyle(
            "StudioBody",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=9.5,
            leading=13,
        )
        section = ParagraphStyle(
            "StudioSection",
            parent=styles["Heading2"],
            fontName=bold_font,
            textColor=_hex(config.primary_color),
            fontSize=13,
            leading=16,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        )
        small = ParagraphStyle("StudioSmall", parent=body, fontSize=7.5, leading=10)

        course = snapshot["course"]
        compliance = snapshot["compliance"]
        student = snapshot["student"]
        certificate = snapshot["certificate"]
        class_data = snapshot["class"]
        story = []
        logo = _image_from_data_uri(config.logo_data_uri, width=42 * mm, height=18 * mm) if config.show_issuer_logo else None
        second_logo = _image_from_data_uri(config.secondary_logo_data_uri, width=34 * mm, height=16 * mm) if config.show_secondary_logo else None
        if logo or second_logo:
            if config.logo_position == "LEFT":
                row = [logo or "", "", second_logo or ""]
            elif config.logo_position == "RIGHT":
                row = [second_logo or "", "", logo or ""]
            else:
                row = [second_logo or "", logo or "", ""]
            logo_table = Table([row], colWidths=[55 * mm, 65 * mm, 55 * mm])
            logo_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.extend([logo_table, Spacer(1, 3 * mm)])

        story.extend(
            [
                Paragraph("CERTIFICADO DE TREINAMENTO", title),
                Paragraph(f"Certificamos que <b>{escape(student['full_name'])}</b> concluiu o treinamento", centered),
                Spacer(1, 4 * mm),
                Paragraph(f"<b>{escape(course['name'])}</b>", title),
                Paragraph(
                    f"Código: {escape(str(course.get('code') or '-'))} &nbsp;|&nbsp; Carga horária: {escape(str(course['workload_hours']))} h &nbsp;|&nbsp; Modalidade: {escape(str(course['modality']))}",
                    centered,
                ),
                Spacer(1, 3 * mm),
                Paragraph(
                    f"Referência regulatória: <b>{escape(compliance['regulatory_standard'])}</b> — versão {escape(str(compliance['regulatory_version']))}",
                    centered,
                ),
                Spacer(1, 4 * mm),
                Paragraph(
                    f"Período: {escape(class_data['start_date'])} a {escape(class_data['end_date'])}" + (f" — Local: {escape(class_data['location'])}" if class_data.get('location') else ""),
                    centered,
                ),
                Spacer(1, 7 * mm),
            ]
        )

        qr = QrCodeWidget(snapshot["validation_url"])
        bounds = qr.getBounds()
        size = 32 * mm
        drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
        drawing.add(qr)
        details = Paragraph(
            f"Certificado: <b>{escape(certificate['number'])}</b><br/>Código de validação: <b>{escape(certificate['validation_code'])}</b><br/>Versão: {certificate['version']}<br/>Emitido em: {escape(certificate['issued_at'])}<br/>Validação pública: {escape(snapshot['validation_url'])}",
            body,
        )
        cells = [drawing, details] if config.qr_position == "LEFT" else [details, drawing]
        info = Table([cells], colWidths=[40 * mm, 130 * mm] if config.qr_position == "LEFT" else [130 * mm, 40 * mm])
        info.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.7, _hex(config.accent_color)),
                    ("BACKGROUND", (0, 0), (-1, -1), _hex(config.background_color)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        story.append(info)
        if config.show_verification_seal:
            story.extend([Spacer(1, 3 * mm), Paragraph("✓ Documento verificável por QR e código público", centered)])
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph(f"Snapshot SHA-256: {snapshot_sha256}<br/>Ledger SHA-256: {snapshot['training_evidence']['ledger_sha256']}", small),
                PageBreak(),
                Paragraph("REGISTRO PEDAGÓGICO E RESPONSÁVEIS", title),
                Paragraph("Conteúdo programático", section),
            ]
        )
        syllabus = snapshot["pedagogical_project"].get("syllabus") or []
        if syllabus:
            for item in syllabus:
                story.append(Paragraph(f"• {escape(str(item))}", body))
        else:
            story.append(Paragraph("Não registrado.", body))
        story.extend([Spacer(1, 2 * mm), Paragraph("Responsável técnico", section)])
        technical = snapshot.get("technical_responsible") or {}
        story.append(
            Paragraph(
                f"<b>{escape(str(technical.get('full_name') or '-'))}</b><br/>Qualificação: {escape(str(technical.get('qualification') or '-'))}<br/>Registro: {escape(str(technical.get('professional_registration') or '-'))} {escape(str(technical.get('council') or ''))}/{escape(str(technical.get('registration_state') or ''))}",
                body,
            )
        )
        story.append(Paragraph("Instrutores", section))
        instructors = snapshot.get("instructors") or []
        if instructors:
            for instructor in instructors:
                story.append(Paragraph(f"<b>{escape(str(instructor.get('full_name') or '-'))}</b> — {escape(str(instructor.get('qualification') or '-'))}", body))
        else:
            story.append(Paragraph("Nenhum instrutor adicional registrado.", body))
        if snapshot.get("assessment"):
            item = snapshot["assessment"]
            story.extend([Paragraph("Avaliação final", section), Paragraph(f"Resultado: satisfatório — nota {item['score']} / mínimo {item['minimum_score']} — concluída em {escape(str(item['completed_at']))}.", body)])
        if snapshot.get("practical_component"):
            item = snapshot["practical_component"]
            story.extend([Paragraph("Componente prático", section), Paragraph(f"Resultado: {escape(str(item['result']))} — realizado em {escape(str(item['performed_at']))} — local: {escape(str(item['location']))}.", body)])
        confirmation = snapshot["student_confirmation"]
        story.extend(
            [
                Paragraph("Confirmação do participante", section),
                Paragraph(f"Declaração {escape(str(confirmation['declaration_version']))}; autenticação {escape(str(confirmation['auth_method']))}; aceita em {escape(str(confirmation['accepted_at']))}.", body),
                Spacer(1, 4 * mm),
                Paragraph(
                    f"Template visual: {escape(str((snapshot.get('certificate_template') or {}).get('template_name') or 'System Default'))} — versão {escape(str((snapshot.get('certificate_template') or {}).get('version') or 1))}. Config SHA-256: {escape(str((snapshot.get('certificate_template') or {}).get('visual_config_sha256') or '-'))}",
                    small,
                ),
                Paragraph("O conteúdo regulatório desta página é gerado exclusivamente a partir do snapshot imutável; o Certificate Studio altera somente a camada visual.", small),
            ]
        )
        callback = lambda canvas, document: cls._page_decorator(canvas, document, config, preview=preview)
        doc.build(story, onFirstPage=callback, onLaterPages=callback)
        return buffer.getvalue()

    @classmethod
    def preview(cls, visual_config: CertificateVisualConfig | dict) -> bytes:
        config = _config_dict(visual_config)
        snapshot = {
            "certificate_template": {"template_name": "Prévia", "version": 1, "visual_config": config, "visual_config_sha256": visual_config_hash(config)},
            "certificate": {"number": "PREVIEW-0001", "validation_code": "PREVIEW-NO-VALIDITY", "version": 1, "issued_at": "2026-08-27T12:00:00", "expires_at": None},
            "issuer": {"name": "Empresa de Treinamentos", "cnpj": "00.000.000/0000-00"},
            "student": {"full_name": "Nome de Exemplo"},
            "course": {"name": "Treinamento Regulatório de Exemplo", "code": "NR-XX", "workload_hours": 8, "modality": "EAD"},
            "class": {"start_date": "2026-08-20", "end_date": "2026-08-27", "location": "Ambiente virtual"},
            "compliance": {"regulatory_standard": "NR-XX", "regulatory_version": "exemplo"},
            "pedagogical_project": {"syllabus": ["Conteúdo programático de exemplo", "Procedimentos seguros", "Avaliação e encerramento"]},
            "technical_responsible": {"full_name": "Responsável Técnico de Exemplo", "qualification": "Qualificação de exemplo", "professional_registration": "REG-0000", "council": "CONSELHO", "registration_state": "UF"},
            "instructors": [{"full_name": "Instrutor de Exemplo", "qualification": "Qualificação de exemplo"}],
            "assessment": {"score": 90, "minimum_score": 60, "completed_at": "2026-08-27T11:30:00"},
            "practical_component": None,
            "student_confirmation": {"declaration_version": "preview-v1", "auth_method": "PASSWORD_RECONFIRMATION", "accepted_at": "2026-08-27T11:35:00"},
            "training_evidence": {"ledger_sha256": "0" * 64},
            "validation_url": "https://example.invalid/validar-certificado?code=PREVIEW-NO-VALIDITY",
        }
        return cls.render(snapshot, snapshot_sha256="0" * 64, preview=True)


class StudioCertificateDocumentService(CertificateDocumentService):
    """Trusted document pipeline with a frozen Certificate Studio visual snapshot."""

    @staticmethod
    async def build_snapshot(
        db: AsyncSession,
        *,
        certificate,
        enrollment,
        student,
        user,
        class_obj,
        course,
        tenant,
    ) -> dict:
        snapshot = await CertificateDocumentService.build_snapshot(
            db,
            certificate=certificate,
            enrollment=enrollment,
            student=student,
            user=user,
            class_obj=class_obj,
            course=course,
            tenant=tenant,
        )
        snapshot["certificate_template"] = await CertificateStudioService.resolve_for_course(
            db,
            tenant_id=certificate.tenant_id,
            course_id=course.id,
        )
        return snapshot

    @staticmethod
    def render_original_pdf(snapshot: dict, *, snapshot_sha256: str) -> bytes:
        return CertificateStudioRenderer.render(snapshot, snapshot_sha256=snapshot_sha256)
