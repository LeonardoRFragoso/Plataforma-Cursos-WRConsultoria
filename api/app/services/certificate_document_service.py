from __future__ import annotations

import hashlib
import io
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.certificate import Certificate, CertificateEvent
from app.models.certificate_document import CertificateDocument, CertificateDocumentStatus
from app.models.class_model import Class
from app.models.compliance import (
    CourseComplianceProfile,
    CourseTrainingProfessional,
    PedagogicalProjectStatus,
    PedagogicalProjectVersion,
    ProfessionalAssignmentRole,
    TrainingProfessional,
)
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.tenant import CustomDomainStatus, Tenant
from app.models.training_evidence import (
    PracticalResult,
    PracticalTrainingRecord,
    RegulatoryCompletionState,
    TrainingAccessEvent,
    TrainingEventType,
)
from app.models.user import User
from app.services.certificate_artifact_storage import (
    load_certificate_pdf,
    remove_certificate_pdf,
    store_certificate_pdf,
)
from app.services.certificate_service import (
    build_validation_url,
    content_hash,
    generate_certificate_number,
    generate_validation_code,
)
from app.services.training_evidence_service import (
    evaluate_regulatory_state,
    record_training_event,
)

SNAPSHOT_VERSION = "1"


@dataclass
class PreparedDocument:
    certificate: Certificate
    document: CertificateDocument
    created: bool


@dataclass
class IntegrityResult:
    artifact: str
    valid: bool
    expected_sha256: str
    actual_sha256: str
    size_bytes: int
    checked_at: datetime
    pdf_bytes: bytes


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


def canonical_json_bytes(payload: dict | list) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(payload: dict | list) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def _professional_snapshot(professional: TrainingProfessional | None) -> dict | None:
    if professional is None:
        return None
    return {
        "id": str(professional.id),
        "full_name": professional.full_name,
        "qualification": professional.qualification,
        "professional_registration": professional.professional_registration,
        "council": professional.council,
        "registration_state": professional.registration_state,
    }


def _public_base_url(tenant: Tenant) -> str:
    if (
        tenant.custom_domain
        and tenant.custom_domain_status == CustomDomainStatus.ACTIVE.value
    ):
        return f"https://{tenant.custom_domain.strip().rstrip('/')}"
    return settings.FRONTEND_URL.rstrip("/")


def _required_snapshot_value(snapshot: dict, field: str):
    field = field.strip().lower()
    mappings = {
        "student_name": lambda: snapshot["student"].get("full_name"),
        "student_cpf": lambda: snapshot["student"].get("cpf"),
        "cpf": lambda: snapshot["student"].get("cpf"),
        "course_name": lambda: snapshot["course"].get("name"),
        "course_code": lambda: snapshot["course"].get("code"),
        "workload": lambda: snapshot["course"].get("workload_hours"),
        "workload_hours": lambda: snapshot["course"].get("workload_hours"),
        "carga_horaria": lambda: snapshot["course"].get("workload_hours"),
        "modality": lambda: snapshot["course"].get("modality"),
        "training_start": lambda: snapshot["class"].get("start_date"),
        "training_end": lambda: snapshot["class"].get("end_date"),
        "training_location": lambda: snapshot["class"].get("location"),
        "regulatory_standard": lambda: snapshot["compliance"].get("regulatory_standard"),
        "regulatory_version": lambda: snapshot["compliance"].get("regulatory_version"),
        "technical_responsible": lambda: snapshot.get("technical_responsible"),
        "instructors": lambda: snapshot.get("instructors"),
        "validation_code": lambda: snapshot["certificate"].get("validation_code"),
        "certificate_number": lambda: snapshot["certificate"].get("number"),
        "issuer_name": lambda: snapshot["issuer"].get("name"),
        "issuer_cnpj": lambda: snapshot["issuer"].get("cnpj"),
        "tenant_cnpj": lambda: snapshot["issuer"].get("cnpj"),
    }
    resolver = mappings.get(field)
    if resolver is None:
        raise ValueError(f"Unsupported certificate required field: {field}")
    return resolver()


def _validate_required_fields(snapshot: dict, required_fields: list[str]) -> None:
    for field in required_fields:
        value = _required_snapshot_value(snapshot, field)
        if value is None or value == "" or value == [] or value == {}:
            raise ValueError(f"Certificate required field is missing: {field}")


class CertificateDocumentService:
    @staticmethod
    async def _context(db: AsyncSession, *, tenant_id: uuid.UUID, enrollment_id: uuid.UUID):
        row = (
            await db.execute(
                select(Enrollment, Student, User, Class, Course, Tenant)
                .join(Student, Enrollment.student_id == Student.id)
                .join(User, Student.user_id == User.id)
                .join(Class, Enrollment.class_id == Class.id)
                .join(Course, Class.course_id == Course.id)
                .join(Tenant, Enrollment.tenant_id == Tenant.id)
                .where(
                    Enrollment.id == enrollment_id,
                    Enrollment.tenant_id == tenant_id,
                    Student.tenant_id == tenant_id,
                    User.tenant_id == tenant_id,
                    Class.tenant_id == tenant_id,
                    Course.tenant_id == tenant_id,
                    Tenant.id == tenant_id,
                )
                .with_for_update(of=Enrollment)
            )
        ).first()
        if not row:
            raise LookupError("Enrollment not found")
        return row

    @staticmethod
    async def _existing_live_document(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment_id: uuid.UUID,
    ) -> tuple[Certificate, CertificateDocument] | None:
        return (
            await db.execute(
                select(Certificate, CertificateDocument)
                .join(
                    CertificateDocument,
                    CertificateDocument.certificate_id == Certificate.id,
                )
                .where(
                    Certificate.tenant_id == tenant_id,
                    Certificate.enrollment_id == enrollment_id,
                    Certificate.status.in_(["PENDING_SIGNATURE", "ACTIVE"]),
                    CertificateDocument.tenant_id == tenant_id,
                )
                .order_by(Certificate.version.desc())
                .limit(1)
            )
        ).first()

    @staticmethod
    async def _create_pending_certificate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: Enrollment,
        student: Student,
        course: Course,
        actor_id: uuid.UUID | None,
        supersedes_id: uuid.UUID | None,
        reason: str | None,
    ) -> Certificate:
        max_version = await db.scalar(
            select(func.coalesce(func.max(Certificate.version), 0)).where(
                Certificate.tenant_id == tenant_id,
                Certificate.enrollment_id == enrollment.id,
            )
        )
        version = int(max_version or 0) + 1
        issued_at = utc_now()
        expires_at = (
            issued_at + timedelta(days=course.certificate_validity_days)
            if course.certificate_validity_days
            else None
        )
        certificate = Certificate(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            certificate_number=generate_certificate_number(demo=False),
            validation_code=generate_validation_code(),
            issued_at=issued_at,
            expires_at=expires_at,
            status="PENDING_SIGNATURE",
            version=version,
            supersedes_id=supersedes_id,
        )
        certificate.content_hash = content_hash(
            certificate_number=certificate.certificate_number,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            student_id=student.id,
            course_id=course.id,
            issued_at=issued_at,
            version=version,
        )
        db.add(certificate)
        await db.flush()
        db.add(
            CertificateEvent(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                event_type="PENDING_SIGNATURE",
                actor_id=actor_id,
                reason=reason,
                details=(
                    f"version={version};registry_hash={certificate.content_hash};"
                    "source=trusted_document_pipeline"
                ),
            )
        )
        return certificate

    @staticmethod
    async def build_snapshot(
        db: AsyncSession,
        *,
        certificate: Certificate,
        enrollment: Enrollment,
        student: Student,
        user: User,
        class_obj: Class,
        course: Course,
        tenant: Tenant,
    ) -> dict:
        tenant_id = certificate.tenant_id
        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == tenant_id,
                    CourseComplianceProfile.course_id == course.id,
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise ValueError("Regulatory compliance profile is required")
        if not class_obj.pedagogical_project_version_id:
            raise ValueError("Class has no pinned pedagogical project version")

        project = (
            await db.execute(
                select(PedagogicalProjectVersion).where(
                    PedagogicalProjectVersion.id == class_obj.pedagogical_project_version_id,
                    PedagogicalProjectVersion.tenant_id == tenant_id,
                    PedagogicalProjectVersion.course_id == course.id,
                )
            )
        ).scalar_one_or_none()
        if not project or project.status not in {
            PedagogicalProjectStatus.APPROVED,
            PedagogicalProjectStatus.ARCHIVED,
        }:
            raise ValueError("Pinned pedagogical project is not an approved historical version")

        technical = None
        if profile.technical_responsible_id:
            technical = (
                await db.execute(
                    select(TrainingProfessional).where(
                        TrainingProfessional.id == profile.technical_responsible_id,
                        TrainingProfessional.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
        if technical is None:
            raise ValueError("Technical responsible snapshot is unavailable")

        assigned_rows = (
            await db.execute(
                select(CourseTrainingProfessional, TrainingProfessional)
                .join(
                    TrainingProfessional,
                    CourseTrainingProfessional.professional_id == TrainingProfessional.id,
                )
                .where(
                    CourseTrainingProfessional.tenant_id == tenant_id,
                    CourseTrainingProfessional.course_id == course.id,
                    TrainingProfessional.tenant_id == tenant_id,
                )
                .order_by(CourseTrainingProfessional.created_at.asc())
            )
        ).all()
        instructors = [
            {
                **(_professional_snapshot(professional) or {}),
                "role": assignment.role,
            }
            for assignment, professional in assigned_rows
            if assignment.role == ProfessionalAssignmentRole.INSTRUCTOR
        ]

        assessment = None
        if profile.requires_final_assessment:
            passed_attempt = (
                await db.execute(
                    select(AssessmentAttempt)
                    .where(
                        AssessmentAttempt.tenant_id == tenant_id,
                        AssessmentAttempt.enrollment_id == enrollment.id,
                        AssessmentAttempt.passed.is_(True),
                        AssessmentAttempt.completed_at.is_not(None),
                    )
                    .order_by(
                        AssessmentAttempt.completed_at.desc(),
                        AssessmentAttempt.attempt_number.desc(),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not passed_attempt:
                raise ValueError("Passing assessment snapshot is unavailable")
            assessment = {
                "attempt_id": str(passed_attempt.id),
                "attempt_number": passed_attempt.attempt_number,
                "question_version": passed_attempt.question_version,
                "score": passed_attempt.score,
                "minimum_score": passed_attempt.minimum_score,
                "passed": passed_attempt.passed,
                "completed_at": _json_value(passed_attempt.completed_at),
            }

        practical = None
        if profile.requires_practical_component:
            practical_record = (
                await db.execute(
                    select(PracticalTrainingRecord)
                    .where(
                        PracticalTrainingRecord.tenant_id == tenant_id,
                        PracticalTrainingRecord.enrollment_id == enrollment.id,
                    )
                    .order_by(
                        PracticalTrainingRecord.created_at.desc(),
                        PracticalTrainingRecord.performed_at.desc(),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not practical_record or practical_record.result != PracticalResult.SATISFACTORY:
                raise ValueError("Current satisfactory practical record is unavailable")
            practical = {
                "record_id": str(practical_record.id),
                "result": practical_record.result,
                "performed_at": _json_value(practical_record.performed_at),
                "duration_minutes": practical_record.duration_minutes,
                "location": practical_record.location,
                "notes": practical_record.notes,
                "instructor_snapshot": practical_record.instructor_snapshot,
                "recorded_at": _json_value(practical_record.created_at),
            }

        confirmation = (
            await db.execute(
                select(StudentSignatureEvidence).where(
                    StudentSignatureEvidence.tenant_id == tenant_id,
                    StudentSignatureEvidence.enrollment_id == enrollment.id,
                    StudentSignatureEvidence.student_id == student.id,
                )
            )
        ).scalar_one_or_none()
        if confirmation is None:
            raise ValueError("Student completion confirmation is unavailable")

        events = list(
            (
                await db.execute(
                    select(TrainingAccessEvent)
                    .where(
                        TrainingAccessEvent.tenant_id == tenant_id,
                        TrainingAccessEvent.enrollment_id == enrollment.id,
                    )
                    .order_by(
                        TrainingAccessEvent.occurred_at.asc(),
                        TrainingAccessEvent.created_at.asc(),
                        TrainingAccessEvent.id.asc(),
                    )
                )
            ).scalars().all()
        )
        ledger_payload = [
            {
                "event_type": item.event_type,
                "occurred_at": _json_value(item.occurred_at),
                "lesson_id": _json_value(item.lesson_id),
                "actor_user_id": _json_value(item.actor_user_id),
                "session_id": _json_value(item.session_id),
                "client_fingerprint": item.client_fingerprint,
                "details": item.details or {},
            }
            for item in events
        ]

        admin = (
            await db.execute(
                select(User).where(
                    User.id == class_obj.responsible_admin_id,
                    User.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        required_fields = [str(item) for item in (profile.certificate_required_fields or [])]
        include_cpf = any(
            item.strip().lower() in {"cpf", "student_cpf"}
            for item in required_fields
        )
        snapshot = {
            "snapshot_version": SNAPSHOT_VERSION,
            "captured_at": utc_now().isoformat(),
            "certificate": {
                "id": str(certificate.id),
                "number": certificate.certificate_number,
                "validation_code": certificate.validation_code,
                "version": certificate.version,
                "registry_hash": certificate.content_hash,
                "issued_at": certificate.issued_at.isoformat(),
                "expires_at": _json_value(certificate.expires_at),
                "supersedes_id": _json_value(certificate.supersedes_id),
            },
            "issuer": {
                "tenant_id": str(tenant.id),
                "name": tenant.name,
                "legal_name": tenant.legal_name,
                "cnpj": tenant.cnpj,
                "logo_url": tenant.logo_url,
                "primary_color": tenant.primary_color,
            },
            "student": {
                "student_id": str(student.id),
                "user_id": str(user.id),
                "full_name": user.full_name,
                **({"cpf": student.cpf} if include_cpf else {}),
            },
            "course": {
                "id": str(course.id),
                "code": course.code,
                "name": course.name,
                "category": course.category,
                "workload_hours": course.carga_horaria,
                "modality": _json_value(course.modality),
                "course_type": _json_value(course.tipo_curso),
            },
            "class": {
                "id": str(class_obj.id),
                "start_date": class_obj.start_date.isoformat(),
                "end_date": class_obj.end_date.isoformat(),
                "location": class_obj.location,
                "ead_link_present": bool(class_obj.ead_link),
                "responsible_admin": (
                    {"id": str(admin.id), "full_name": admin.full_name}
                    if admin
                    else None
                ),
                "pedagogical_project_version_id": str(project.id),
            },
            "compliance": {
                "profile_id": str(profile.id),
                "regulatory_standard": profile.regulatory_standard,
                "regulatory_version": profile.regulatory_version,
                "delivery_mode": profile.delivery_mode,
                "requires_final_assessment": profile.requires_final_assessment,
                "minimum_score": profile.minimum_score,
                "requires_practical_component": profile.requires_practical_component,
                "validity_period_months": profile.validity_period_months,
                "prerequisites": profile.prerequisites,
                "certificate_required_fields": required_fields,
                "last_compliance_review_at": _json_value(profile.last_compliance_review_at),
                "next_compliance_review_at": _json_value(profile.next_compliance_review_at),
            },
            "pedagogical_project": {
                "id": str(project.id),
                "version": project.version,
                "approved_at": _json_value(project.approved_at),
                "workload_hours": project.workload_hours,
                "delivery_mode": project.delivery_mode,
                "general_objective": project.general_objective,
                "specific_objectives": project.specific_objectives or [],
                "target_audience": project.target_audience,
                "teaching_strategy": project.teaching_strategy,
                "syllabus": project.syllabus or [],
                "materials": project.materials or [],
                "assessment_methodology": project.assessment_methodology,
            },
            "technical_responsible": _professional_snapshot(technical),
            "instructors": instructors,
            "assessment": assessment,
            "practical_component": practical,
            "student_confirmation": {
                "evidence_id": str(confirmation.id),
                "assessment_attempt_id": _json_value(confirmation.assessment_attempt_id),
                "declaration_version": confirmation.declaration_version,
                "auth_method": confirmation.auth_method,
                "accepted_at": _json_value(confirmation.accepted_at),
            },
            "training_evidence": {
                "event_count": len(ledger_payload),
                "first_event_at": (
                    _json_value(events[0].occurred_at) if events else None
                ),
                "last_event_at": (
                    _json_value(events[-1].occurred_at) if events else None
                ),
                "ledger_sha256": sha256_json(ledger_payload),
            },
            "validation_url": build_validation_url(
                _public_base_url(tenant), certificate.validation_code
            ),
        }
        _validate_required_fields(snapshot, required_fields)
        return snapshot

    @staticmethod
    def render_original_pdf(snapshot: dict, *, snapshot_sha256: str) -> bytes:
        """Render the stable pre-signature regulatory artifact.

        Certificate Studio will own configurable visual templates later. This
        renderer intentionally prioritizes deterministic facts, readability,
        validation identifiers and the complete regulatory appendix.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"Certificate {snapshot['certificate']['number']}",
            author=snapshot["issuer"]["name"],
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "CertificateTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            leading=24,
            spaceAfter=8 * mm,
        )
        centered = ParagraphStyle(
            "Centered",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=11,
            leading=16,
        )
        section = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        )
        small = ParagraphStyle(
            "Small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
        )

        course = snapshot["course"]
        compliance = snapshot["compliance"]
        student = snapshot["student"]
        certificate = snapshot["certificate"]
        class_data = snapshot["class"]
        story = [
            Paragraph("CERTIFICADO DE TREINAMENTO", title),
            Paragraph(
                f"Certificamos que <b>{escape(student['full_name'])}</b> concluiu o treinamento",
                centered,
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>{escape(course['name'])}</b>", title),
            Paragraph(
                (
                    f"Código: {escape(str(course.get('code') or '-'))} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"Carga horária: {escape(str(course['workload_hours']))} h &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"Modalidade: {escape(str(course['modality']))}"
                ),
                centered,
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                (
                    f"Referência regulatória: <b>{escape(compliance['regulatory_standard'])}</b> "
                    f"— versão {escape(compliance['regulatory_version'])}"
                ),
                centered,
            ),
            Spacer(1, 5 * mm),
            Paragraph(
                (
                    f"Período da turma: {escape(class_data['start_date'])} a "
                    f"{escape(class_data['end_date'])}"
                    + (
                        f" — Local: {escape(class_data['location'])}"
                        if class_data.get("location")
                        else ""
                    )
                ),
                centered,
            ),
            Spacer(1, 8 * mm),
        ]

        qr = QrCodeWidget(snapshot["validation_url"])
        bounds = qr.getBounds()
        size = 34 * mm
        drawing = Drawing(size, size, transform=[
            size / (bounds[2] - bounds[0]),
            0,
            0,
            size / (bounds[3] - bounds[1]),
            0,
            0,
        ])
        drawing.add(qr)
        info = Table(
            [
                [
                    Paragraph(
                        (
                            f"Certificado: <b>{escape(certificate['number'])}</b><br/>"
                            f"Código de validação: <b>{escape(certificate['validation_code'])}</b><br/>"
                            f"Versão: {certificate['version']}<br/>"
                            f"Emitido em: {escape(certificate['issued_at'])}<br/>"
                            f"Validação pública: {escape(snapshot['validation_url'])}"
                        ),
                        styles["BodyText"],
                    ),
                    drawing,
                ]
            ],
            colWidths=[130 * mm, 40 * mm],
        )
        info.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        story.extend(
            [
                info,
                Spacer(1, 5 * mm),
                Paragraph(
                    (
                        f"Snapshot SHA-256: {snapshot_sha256}<br/>"
                        f"Ledger SHA-256: {snapshot['training_evidence']['ledger_sha256']}"
                    ),
                    small,
                ),
                PageBreak(),
                Paragraph("REGISTRO PEDAGÓGICO E RESPONSÁVEIS", title),
                Paragraph("Conteúdo programático", section),
            ]
        )
        syllabus = snapshot["pedagogical_project"].get("syllabus") or []
        if syllabus:
            for item in syllabus:
                story.append(Paragraph(f"• {escape(str(item))}", styles["BodyText"]))
        else:
            story.append(Paragraph("Não registrado.", styles["BodyText"]))

        story.extend([Spacer(1, 3 * mm), Paragraph("Responsável técnico", section)])
        technical = snapshot.get("technical_responsible") or {}
        story.append(
            Paragraph(
                (
                    f"<b>{escape(str(technical.get('full_name') or '-'))}</b><br/>"
                    f"Qualificação: {escape(str(technical.get('qualification') or '-'))}<br/>"
                    f"Registro: {escape(str(technical.get('professional_registration') or '-'))} "
                    f"{escape(str(technical.get('council') or ''))}/"
                    f"{escape(str(technical.get('registration_state') or ''))}"
                ),
                styles["BodyText"],
            )
        )

        story.append(Paragraph("Instrutores", section))
        instructors = snapshot.get("instructors") or []
        if instructors:
            for instructor in instructors:
                story.append(
                    Paragraph(
                        (
                            f"<b>{escape(str(instructor.get('full_name') or '-'))}</b> — "
                            f"{escape(str(instructor.get('qualification') or '-'))}"
                        ),
                        styles["BodyText"],
                    )
                )
        else:
            story.append(Paragraph("Nenhum instrutor adicional registrado.", styles["BodyText"]))

        if snapshot.get("assessment"):
            item = snapshot["assessment"]
            story.extend(
                [
                    Paragraph("Avaliação final", section),
                    Paragraph(
                        (
                            f"Resultado: satisfatório — nota {item['score']} / mínimo "
                            f"{item['minimum_score']} — concluída em {escape(str(item['completed_at']))}."
                        ),
                        styles["BodyText"],
                    ),
                ]
            )
        if snapshot.get("practical_component"):
            item = snapshot["practical_component"]
            story.extend(
                [
                    Paragraph("Componente prático", section),
                    Paragraph(
                        (
                            f"Resultado: {escape(str(item['result']))} — realizado em "
                            f"{escape(str(item['performed_at']))} — local: "
                            f"{escape(str(item['location']))}."
                        ),
                        styles["BodyText"],
                    ),
                ]
            )

        confirmation = snapshot["student_confirmation"]
        story.extend(
            [
                Paragraph("Confirmação do participante", section),
                Paragraph(
                    (
                        f"Declaração {escape(str(confirmation['declaration_version']))}; "
                        f"autenticação {escape(str(confirmation['auth_method']))}; aceita em "
                        f"{escape(str(confirmation['accepted_at']))}."
                    ),
                    styles["BodyText"],
                ),
                Spacer(1, 5 * mm),
                Paragraph(
                    (
                        "Este PDF é o artefato original imutável preparado pela plataforma. "
                        "A validade criptográfica da assinatura é representada separadamente "
                        "pelo estado do documento e pelo hash do artefato assinado."
                    ),
                    small,
                ),
            ]
        )
        doc.build(story)
        return buffer.getvalue()

    @classmethod
    async def prepare_document(
        cls,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        supersedes_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> PreparedDocument:
        enrollment, student, user, class_obj, course, tenant = await cls._context(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment_id,
        )

        existing = await cls._existing_live_document(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
        )
        if existing:
            certificate, document = existing
            return PreparedDocument(certificate=certificate, document=document, created=False)

        evaluation = await evaluate_regulatory_state(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            persist=True,
        )
        if evaluation.state != RegulatoryCompletionState.CERTIFICATE_PENDING_SIGNATURE:
            raise ValueError(
                "Enrollment is not ready for trusted certificate preparation: "
                f"{evaluation.state}"
            )

        active = (
            await db.execute(
                select(Certificate.id).where(
                    Certificate.tenant_id == tenant_id,
                    Certificate.enrollment_id == enrollment.id,
                    Certificate.status == "ACTIVE",
                )
            )
        ).scalar_one_or_none()
        if active:
            raise ValueError("Enrollment already has an active certificate")

        original_storage_key = None
        try:
            certificate = await cls._create_pending_certificate(
                db,
                tenant_id=tenant_id,
                enrollment=enrollment,
                student=student,
                course=course,
                actor_id=actor_id,
                supersedes_id=supersedes_id,
                reason=reason,
            )
            snapshot = await cls.build_snapshot(
                db,
                certificate=certificate,
                enrollment=enrollment,
                student=student,
                user=user,
                class_obj=class_obj,
                course=course,
                tenant=tenant,
            )
            snapshot_hash = sha256_json(snapshot)
            pdf_bytes = cls.render_original_pdf(snapshot, snapshot_sha256=snapshot_hash)
            pdf_hash = sha256_bytes(pdf_bytes)
            original_storage_key = await store_certificate_pdf(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                pdf_bytes=pdf_bytes,
                sha256=pdf_hash,
                signed=False,
            )
            document = CertificateDocument(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                enrollment_id=enrollment.id,
                status=CertificateDocumentStatus.PENDING_SIGNATURE,
                snapshot_version=SNAPSHOT_VERSION,
                snapshot=snapshot,
                snapshot_sha256=snapshot_hash,
                original_storage_key=original_storage_key,
                original_pdf_sha256=pdf_hash,
                original_size_bytes=len(pdf_bytes),
                rendered_at=utc_now(),
            )
            db.add(document)
            await db.flush()
            db.add(
                CertificateEvent(
                    tenant_id=tenant_id,
                    certificate_id=certificate.id,
                    event_type="DOCUMENT_PREPARED",
                    actor_id=actor_id,
                    reason=reason,
                    details=(
                        f"snapshot_sha256={snapshot_hash};pdf_sha256={pdf_hash};"
                        f"size={len(pdf_bytes)}"
                    ),
                )
            )
            await db.commit()
            await db.refresh(certificate)
            await db.refresh(document)
            return PreparedDocument(certificate=certificate, document=document, created=True)
        except IntegrityError:
            await db.rollback()
            await remove_certificate_pdf(original_storage_key)
            existing = await cls._existing_live_document(
                db,
                tenant_id=tenant_id,
                enrollment_id=enrollment_id,
            )
            if existing:
                certificate, document = existing
                return PreparedDocument(certificate=certificate, document=document, created=False)
            raise
        except Exception:
            await db.rollback()
            await remove_certificate_pdf(original_storage_key)
            raise

    @staticmethod
    async def verify_integrity(
        *,
        document: CertificateDocument,
        original: bool = False,
    ) -> IntegrityResult:
        if not original and document.status == CertificateDocumentStatus.SIGNED:
            storage_key = document.signed_storage_key
            expected = document.signed_pdf_sha256
            artifact = "SIGNED"
        else:
            storage_key = document.original_storage_key
            expected = document.original_pdf_sha256
            artifact = "ORIGINAL"
        if not storage_key or not expected:
            raise ValueError("Requested certificate artifact is unavailable")
        pdf_bytes = await load_certificate_pdf(storage_key)
        actual = sha256_bytes(pdf_bytes)
        return IntegrityResult(
            artifact=artifact,
            valid=actual == expected,
            expected_sha256=expected,
            actual_sha256=actual,
            size_bytes=len(pdf_bytes),
            checked_at=utc_now(),
            pdf_bytes=pdf_bytes,
        )

    @classmethod
    async def finalize_signed_document(
        cls,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        certificate_id: uuid.UUID,
        signed_pdf_bytes: bytes,
        provider: str,
        signature_metadata: dict | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> CertificateDocument:
        """Persist a signer-produced PDF and activate its certificate.

        No HTTP route calls this method yet. The future PAdES/ICP-Brasil
        provider adapter is expected to call it only after independently
        validating the provider response/signature. This method deliberately
        does not claim to verify ICP-Brasil cryptography by itself.
        """
        provider = provider.strip()
        if not provider:
            raise ValueError("Signature provider is required")
        if not signed_pdf_bytes.startswith(b"%PDF"):
            raise ValueError("Signed artifact must be a PDF")

        row = (
            await db.execute(
                select(CertificateDocument, Certificate, Enrollment, Class)
                .join(Certificate, CertificateDocument.certificate_id == Certificate.id)
                .join(Enrollment, CertificateDocument.enrollment_id == Enrollment.id)
                .join(Class, Enrollment.class_id == Class.id)
                .where(
                    CertificateDocument.tenant_id == tenant_id,
                    CertificateDocument.certificate_id == certificate_id,
                    Certificate.tenant_id == tenant_id,
                    Enrollment.tenant_id == tenant_id,
                    Class.tenant_id == tenant_id,
                )
                .with_for_update(of=CertificateDocument)
            )
        ).first()
        if not row:
            raise LookupError("Certificate document not found")
        document, certificate, enrollment, class_obj = row
        if document.status == CertificateDocumentStatus.SIGNED:
            return document
        if certificate.status != "PENDING_SIGNATURE":
            raise ValueError("Certificate is not pending signature")

        signed_hash = sha256_bytes(signed_pdf_bytes)
        if signed_hash == document.original_pdf_sha256:
            raise ValueError("Signed artifact must differ from the original PDF bytes")

        signed_storage_key = None
        try:
            signed_storage_key = await store_certificate_pdf(
                tenant_id=tenant_id,
                certificate_id=certificate.id,
                pdf_bytes=signed_pdf_bytes,
                sha256=signed_hash,
                signed=True,
            )
            signed_at = utc_now()
            document.signed_storage_key = signed_storage_key
            document.signed_pdf_sha256 = signed_hash
            document.signed_size_bytes = len(signed_pdf_bytes)
            document.signature_provider = provider
            document.signature_metadata = signature_metadata or {}
            document.signed_at = signed_at
            document.status = CertificateDocumentStatus.SIGNED

            certificate.status = "ACTIVE"
            certificate.pdf_path = signed_storage_key
            db.add(
                CertificateEvent(
                    tenant_id=tenant_id,
                    certificate_id=certificate.id,
                    event_type="SIGNED",
                    actor_id=actor_id,
                    details=(
                        f"provider={provider};signed_pdf_sha256={signed_hash};"
                        f"size={len(signed_pdf_bytes)}"
                    ),
                )
            )
            await record_training_event(
                db,
                tenant_id=tenant_id,
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                course_id=class_obj.course_id,
                actor_user_id=actor_id,
                event_type=TrainingEventType.CERTIFICATE_ISSUED,
                details={
                    "certificate_id": str(certificate.id),
                    "document_id": str(document.id),
                    "provider": provider,
                    "signed_pdf_sha256": signed_hash,
                },
            )
            await evaluate_regulatory_state(
                db,
                tenant_id=tenant_id,
                enrollment_id=enrollment.id,
                persist=True,
            )
            await db.commit()
            await db.refresh(document)
            return document
        except Exception:
            await db.rollback()
            await remove_certificate_pdf(signed_storage_key)
            raise
