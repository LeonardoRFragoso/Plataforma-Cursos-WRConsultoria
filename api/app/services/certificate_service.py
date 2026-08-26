"""Certificate domain service.

Centralises the reusable business rules for certificate issuance, the
public validation journey aggregation, and the branded PDF generation
(with QR code). Both the HTTP routes and the administrative demo script
call into this service so the issuance rule is never duplicated.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.certificate import Certificate, CertificateEvent
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, LessonProgress
from app.models.student import Student
from app.schemas.certificate import (
    CertificateJourney,
    JourneyProgress,
    JourneyStep,
)

# WR brand primary green. Used as the fallback when a tenant has no
# primary_color configured.
WR_PRIMARY_COLOR = "#047F37"

DEMO_CERTIFICATE_PREFIX = "DEMO-"


def is_demo_certificate(certificate: Certificate) -> bool:
    """A certificate is a demonstration record when its number is prefixed
    with ``DEMO-``. This avoids an extra database column / migration while
    remaining unambiguous and impossible to collide with real certificate
    numbers (which use the ``CERT-`` prefix)."""
    return bool(certificate.certificate_number) and certificate.certificate_number.startswith(
        DEMO_CERTIFICATE_PREFIX
    )


def generate_certificate_number(*, demo: bool = False) -> str:
    prefix = DEMO_CERTIFICATE_PREFIX if demo else "CERT-"
    return f"{prefix}{uuid.uuid4().hex[:12].upper()}"


def generate_validation_code() -> str:
    return uuid.uuid4().hex[:16].upper()


def effective_status(certificate: Certificate) -> str:
    if certificate.status == "REVOKED":
        return "REVOKED"
    if certificate.status == "SUPERSEDED":
        return "SUPERSEDED"
    if certificate.expires_at and certificate.expires_at <= utc_now():
        return "EXPIRED"
    return "ACTIVE"


def content_hash(
    *,
    certificate_number: str,
    tenant_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    issued_at: datetime,
    version: int,
) -> str:
    """SHA-256 of the structured issuance record (NOT of the PDF bytes).

    This is the *registry* hash — it proves the issuance metadata is
    intact. A future ``pdf_sha256`` would be a separate property.
    """
    payload = "|".join(
        [
            certificate_number,
            str(tenant_id),
            str(enrollment_id),
            str(student_id),
            str(course_id),
            issued_at.isoformat(),
            str(version),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_validation_url(frontend_url: str, validation_code: str) -> str:
    """Build the public validation URL the QR code points to.

    Uses the real public frontend route ``/validar-certificado`` with the
    ``codigo`` query parameter (``code`` is also accepted by the frontend
    for backwards compatibility, but the canonical emitted URL uses
    ``codigo``).
    """
    base = frontend_url.rstrip("/")
    return f"{base}/validar-certificado?codigo={validation_code}"


@dataclass
class IssuanceInputs:
    """Resolved context needed to issue a certificate."""

    enrollment: Enrollment
    student: Student
    course_id: uuid.UUID
    course_validity_days: int | None


class CertificateService:
    # --- Issuance (shared by route + demo script) -----------------------

    @staticmethod
    async def issue_certificate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: Enrollment,
        student: Student,
        course_id: uuid.UUID,
        course_validity_days: int | None,
        actor_id: uuid.UUID | None,
        supersedes_id: uuid.UUID | None = None,
        reason: str | None = None,
        demo: bool = False,
    ) -> Certificate:
        """Create a certificate record + ISSUED/REISSUED event.

        Does NOT bypass the "completed enrollment" rule — callers are
        responsible for ensuring the enrollment is CONCLUIDA (the route
        enforces it; the demo script simulates the full academic path
        before calling this).
        """
        max_version = await db.scalar(
            select(func.coalesce(func.max(Certificate.version), 0)).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
            )
        )
        version = int(max_version or 0) + 1
        issued_at = utc_now()
        expires_at = (
            issued_at + timedelta(days=course_validity_days)
            if course_validity_days
            else None
        )
        certificate = Certificate(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            certificate_number=generate_certificate_number(demo=demo),
            validation_code=generate_validation_code(),
            issued_at=issued_at,
            expires_at=expires_at,
            status="ACTIVE",
            version=version,
            supersedes_id=supersedes_id,
        )
        certificate.content_hash = content_hash(
            certificate_number=certificate.certificate_number,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=course_id,
            issued_at=issued_at,
            version=version,
        )
        db.add(certificate)
        await db.flush()
        event_type = "DEMO_ISSUED" if demo else ("REISSUED" if supersedes_id else "ISSUED")
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                event_type=event_type,
                actor_id=actor_id,
                reason=reason,
                details=f"version={version};hash={certificate.content_hash}",
            )
        )
        return certificate

    # --- Journey aggregation (public, privacy-safe) ---------------------

    @staticmethod
    async def build_journey(
        db: AsyncSession,
        *,
        certificate: Certificate,
        enrollment: Enrollment,
        student: Student,
        course_id: uuid.UUID,
        course_name: str,
    ) -> CertificateJourney:
        """Derive the academic timeline from REAL recorded data.

        Nothing is invented: if a step cannot be determined it is omitted
        or marked "Informação não registrada".
        """
        order = 0
        steps: list[JourneyStep] = []
        lessons_steps: list[JourneyStep] = []

        # 1. Enrollment
        if enrollment.enrollment_date:
            order += 1
            steps.append(
                JourneyStep(
                    type="ENROLLED",
                    label="Matrícula confirmada",
                    description=f"Matrícula realizada em {course_name}.",
                    occurred_at=enrollment.enrollment_date,
                    order=order,
                )
            )

        # Required lessons for the course
        required_lessons = (
            await db.execute(
                select(Lesson)
                .where(
                    Lesson.tenant_id == certificate.tenant_id,
                    Lesson.course_id == course_id,
                    Lesson.is_required.is_(True),
                )
                .order_by(Lesson.order, Lesson.created_at)
            )
        ).scalars().all()
        required_ids = [lesson.id for lesson in required_lessons]
        required_total = len(required_ids)

        # Progress for this student on these lessons
        progresses: list[LessonProgress] = []
        if required_ids:
            progresses = list(
                (
                    await db.execute(
                        select(LessonProgress)
                        .where(
                            LessonProgress.tenant_id == certificate.tenant_id,
                            LessonProgress.student_id == student.id,
                            LessonProgress.lesson_id.in_(required_ids),
                        )
                        .order_by(LessonProgress.completed_at, LessonProgress.created_at)
                    )
                ).scalars().all()
            )
        completed = [p for p in progresses if p.completed]
        required_completed = len(completed)
        completion_percent = (
            round(100.0 * required_completed / required_total, 1) if required_total else 0.0
        )

        # 2. Course started — first real progress record
        started_at = None
        if progresses:
            started_at = min(p.created_at for p in progresses)
        elif enrollment.enrollment_date:
            started_at = enrollment.enrollment_date
        if started_at:
            order += 1
            steps.append(
                JourneyStep(
                    type="COURSE_STARTED",
                    label="Curso iniciado",
                    occurred_at=started_at,
                    order=order,
                )
            )

        # 3. Per-lesson completion steps (expandable detail)
        lesson_lookup = {lesson.id: lesson for lesson in required_lessons}
        for prog in sorted(completed, key=lambda p: p.completed_at or p.updated_at):
            lesson = lesson_lookup.get(prog.lesson_id)
            if not lesson:
                continue
            lessons_steps.append(
                JourneyStep(
                    type="LESSON_COMPLETED",
                    label=f"Aula concluída: {lesson.title}",
                    occurred_at=prog.completed_at,
                    order=0,
                )
            )

        # 4. Progress summary step
        if required_total:
            order += 1
            steps.append(
                JourneyStep(
                    type="LESSON_COMPLETED",
                    label=(
                        f"{required_completed} de {required_total} aulas "
                        f"obrigatórias concluídas"
                    ),
                    description=f"{completion_percent}% de aproveitamento",
                    occurred_at=completed[-1].completed_at if completed else None,
                    order=order,
                )
            )

        # 5. Course completed — only when 100% of required lessons done
        if required_total and required_completed >= required_total:
            last_completed_at = max(
                (p.completed_at for p in completed if p.completed_at), default=None
            )
            order += 1
            steps.append(
                JourneyStep(
                    type="COURSE_COMPLETED",
                    label="Curso concluído",
                    occurred_at=last_completed_at,
                    order=order,
                )
            )
        elif enrollment.status == EnrollmentStatus.CONCLUIDA:
            # No lesson data but enrollment marked complete — record the
            # step without inventing a timestamp.
            order += 1
            steps.append(
                JourneyStep(
                    type="COURSE_COMPLETED",
                    label="Curso concluído",
                    description="Informação não registrada",
                    order=order,
                )
            )

        # 6. Certificate issued
        order += 1
        steps.append(
            JourneyStep(
                type="CERTIFICATE_ISSUED",
                label="Certificado emitido",
                occurred_at=certificate.issued_at,
                order=order,
            )
        )

        # 7. Lifecycle events (reissue / revoke) from the audit log
        events = (
            await db.execute(
                select(CertificateEvent)
                .where(
                    CertificateEvent.tenant_id == certificate.tenant_id,
                    CertificateEvent.certificate_id == certificate.id,
                )
                .order_by(CertificateEvent.created_at)
            )
        ).scalars().all()
        for event in events:
            if event.event_type in ("REISSUED", "CERTIFICATE_REISSUED"):
                order += 1
                steps.append(
                    JourneyStep(
                        type="CERTIFICATE_REISSUED",
                        label="Certificado reemitido",
                        description=event.reason,
                        occurred_at=event.created_at,
                        order=order,
                    )
                )
            elif event.event_type in ("REVOKED", "CERTIFICATE_REVOKED"):
                order += 1
                steps.append(
                    JourneyStep(
                        type="CERTIFICATE_REVOKED",
                        label="Certificado revogado",
                        description=event.reason,
                        occurred_at=event.created_at,
                        order=order,
                    )
                )

        progress = JourneyProgress(
            required_lessons_total=required_total,
            required_lessons_completed=required_completed,
            completion_percent=completion_percent,
        )
        return CertificateJourney(progress=progress, steps=steps, lessons=lessons_steps)

    # --- PDF generation (branded, with QR) -------------------------------

    @staticmethod
    def generate_certificate_pdf(
        *,
        student_name: str,
        course_name: str,
        course_code: str,
        carga_horaria: int,
        certificate_number: str,
        validation_code: str,
        responsible_admin_name: str,
        brand_name: str,
        validation_url: str,
        issued_date: datetime | None = None,
        brand_primary_color: str | None = None,
        brand_logo_url: str | None = None,
        is_demo: bool = False,
    ) -> bytes:
        """Generate a professional A4 landscape certificate PDF with a QR
        code that points to the public validation page."""
        if issued_date is None:
            issued_date = utc_now()

        try:
            primary = colors.HexColor(brand_primary_color or WR_PRIMARY_COLOR)
        except (ValueError, TypeError):
            primary = colors.HexColor(WR_PRIMARY_COLOR)
        primary_dark = colors.HexColor("#036B2E")
        light_bg = colors.HexColor("#F4F9F5")
        border_color = colors.HexColor("#D1E7DA")
        muted = colors.HexColor("#6B7280")

        buffer = io.BytesIO()
        page = landscape(A4)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CertTitle",
            parent=styles["Heading1"],
            fontSize=30,
            textColor=primary,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            leading=34,
        )
        subtitle_style = ParagraphStyle(
            "CertSubtitle",
            parent=styles["Normal"],
            fontSize=12,
            textColor=muted,
            alignment=TA_CENTER,
            fontName="Helvetica",
            spaceAfter=2,
            letterSpacing=2,
        )
        body_style = ParagraphStyle(
            "CertBody",
            parent=styles["BodyText"],
            fontSize=13,
            textColor=colors.HexColor("#1F2937"),
            alignment=TA_CENTER,
            spaceAfter=6,
            leading=18,
        )
        student_style = ParagraphStyle(
            "CertStudent",
            parent=styles["Heading2"],
            fontSize=24,
            textColor=primary_dark,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            leading=28,
        )
        course_style = ParagraphStyle(
            "CertCourse",
            parent=styles["Heading3"],
            fontSize=18,
            textColor=colors.HexColor("#111827"),
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            spaceAfter=4,
            leading=22,
        )
        meta_style = ParagraphStyle(
            "CertMeta",
            parent=styles["Normal"],
            fontSize=10.5,
            textColor=colors.HexColor("#374151"),
            alignment=TA_CENTER,
            leading=15,
        )
        footer_style = ParagraphStyle(
            "CertFooter",
            parent=styles["Normal"],
            fontSize=9,
            textColor=muted,
            alignment=TA_CENTER,
            leading=12,
        )
        qr_label_style = ParagraphStyle(
            "QrLabel",
            parent=styles["Normal"],
            fontSize=8.5,
            textColor=muted,
            alignment=TA_CENTER,
            leading=11,
        )
        demo_banner_style = ParagraphStyle(
            "DemoBanner",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#B45309"),
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            leading=14,
        )

        elements: list = []

        # Brand header
        elements.append(Paragraph(brand_name.upper(), subtitle_style))
        elements.append(Spacer(1, 4 * mm))

        # Title
        title_text = "CERTIFICADO DE CONCLUSÃO"
        if is_demo:
            title_text = "CERTIFICADO DE TESTE / DEMONSTRAÇÃO"
        elements.append(Paragraph(title_text, title_style))
        elements.append(Spacer(1, 6 * mm))

        # Body
        elements.append(Paragraph("Certificamos que", body_style))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(student_name, student_style))
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("concluiu o treinamento", body_style))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(course_name, course_style))
        elements.append(Spacer(1, 3 * mm))

        meta_line = f"Código: <b>{course_code}</b>&nbsp;&nbsp;&nbsp;Carga horária: <b>{carga_horaria}h</b>"
        elements.append(Paragraph(meta_line, meta_style))
        elements.append(Spacer(1, 2 * mm))

        formatted_date = _format_pt_br(issued_date)
        elements.append(Paragraph(f"Emitido em {formatted_date}", meta_style))
        elements.append(Spacer(1, 8 * mm))

        # QR code
        qr_widget = QrCodeWidget(validation_url, barLevel="M")
        bounds = qr_widget.getBounds()
        qr_w = bounds[2] - bounds[0]
        qr_h = bounds[3] - bounds[1]
        qr_drawing = Drawing(28 * mm, 28 * mm)
        qr_drawing.add(qr_widget)
        # Center the QR inside the drawing
        qr_drawing.scale(28 * mm / qr_w, 28 * mm / qr_h)
        qr_drawing.translate(-bounds[0] * (28 * mm / qr_w), -bounds[1] * (28 * mm / qr_h))

        qr_cell = [
            [qr_drawing],
            [Paragraph("Escaneie para validar", qr_label_style)],
            [Paragraph("online", qr_label_style)],
        ]
        qr_table = Table(qr_cell, colWidths=[34 * mm])
        qr_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        info_cell = [
            [Paragraph(f"<b>Número do certificado:</b> {certificate_number}", footer_style)],
            [Paragraph(f"<b>Código de validação:</b> {validation_code}", footer_style)],
            [Spacer(1, 3 * mm)],
            [Paragraph(f"Responsável: {responsible_admin_name}", footer_style)],
            [Spacer(1, 2 * mm)],
            [Paragraph(f"Emitido por <b>{brand_name}</b>", footer_style)],
            [Spacer(1, 2 * mm)],
            [Paragraph(f"Valide em: {validation_url}", footer_style)],
        ]
        info_table = Table(info_cell, colWidths=[120 * mm])
        info_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        bottom = Table(
            [[info_table, qr_table]],
            colWidths=[doc.width - 40 * mm, 40 * mm],
        )
        bottom.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                    ("BACKGROUND", (0, 0), (-1, -1), light_bg),
                ]
            )
        )
        elements.append(bottom)

        # Demo watermark + banner
        if is_demo:
            elements.append(Spacer(1, 5 * mm))
            elements.append(
                Paragraph(
                    "CERTIFICADO DE TESTE — SEM VALIDADE OFICIAL",
                    demo_banner_style,
                )
            )

        # Build with a decorative border + watermark drawn on the canvas
        doc.build(
            elements,
            onFirstPage=_draw_border_and_watermark(primary, is_demo, page),
            onLaterPages=_draw_border_and_watermark(primary, is_demo, page),
        )
        buffer.seek(0)
        return buffer.getvalue()


def _format_pt_br(dt: datetime) -> str:
    months = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return f"{dt.day} de {months[dt.month - 1]} de {dt.year}"


def _draw_border_and_watermark(primary_color, is_demo: bool, pagesize):
    from reportlab.pdfgen import canvas as canvaslib

    width, height = pagesize

    def _draw(c: canvaslib.Canvas, _doc):
        # Outer decorative border
        c.setStrokeColor(primary_color)
        c.setLineWidth(2.2)
        c.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm, stroke=1, fill=0)
        c.setLineWidth(0.6)
        c.rect(13 * mm, 13 * mm, width - 26 * mm, height - 26 * mm, stroke=1, fill=0)

        if is_demo:
            # Diagonal "DEMONSTRAÇÃO" watermark, repeated, low opacity
            c.saveState()
            c.setFillColor(colors.HexColor("#F59E0B"))
            c.setFillAlpha(0.10)
            c.setFont("Helvetica-Bold", 60)
            c.translate(width / 2, height / 2)
            c.rotate(35)
            for offset in (-220, 0, 220):
                c.drawCentredString(offset, -30, "DEMONSTRAÇÃO")
            c.restoreState()

    return _draw
