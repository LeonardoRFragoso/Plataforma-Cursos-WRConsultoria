from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.assessment import AssessmentAttempt, StudentSignatureEvidence
from app.models.compliance import (
    ComplianceStatus,
    CourseComplianceProfile,
    CourseProfessionalAssignment,
    PedagogicalProjectStatus,
    PedagogicalProjectVersion,
    PracticalCompletionEvidence,
    ProfessionalRole,
    TrainingAccessLog,
    TrainingProfessional,
)
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson, LessonProgress


NR1_CERTIFICATE_FIELDS = {
    "student_name",
    "worker_signature",
    "program_content",
    "workload",
    "training_date",
    "training_location",
    "instructors",
    "instructor_qualifications",
    "technical_responsible_signature",
}


@dataclass
class ComplianceReadiness:
    ready: bool
    issues: list[str]


class ComplianceService:
    """Fail-closed regulatory readiness and audit helpers.

    This service deliberately does not infer legal facts. A course only becomes
    eligible for official certification after the required regulatory data is
    supplied and a qualified professional explicitly approves the profile.
    """

    @staticmethod
    async def readiness(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        course_id: UUID,
    ) -> ComplianceReadiness:
        issues: list[str] = []
        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == tenant_id,
                    CourseComplianceProfile.course_id == course_id,
                )
            )
        ).scalar_one_or_none()
        if not profile:
            return ComplianceReadiness(False, ["Perfil regulatório não cadastrado"])

        if not profile.regulatory_standard.strip():
            issues.append("NR/norma regulatória não informada")
        if not profile.regulatory_version.strip():
            issues.append("Versão normativa não informada")
        if not profile.regulatory_source_url.strip():
            issues.append("Fonte normativa oficial não informada")
        if profile.delivery_mode not in {"EAD", "SEMIPRESENCIAL", "PRESENCIAL"}:
            issues.append("Modalidade de oferta inválida")
        if profile.minimum_score < 0 or profile.minimum_score > 100:
            issues.append("Nota mínima fora do intervalo 0-100")
        if profile.access_log_retention_months_after_validity < 24:
            issues.append("Retenção de logs inferior ao mínimo de 24 meses após a validade")
        if profile.requires_practical_component and not (profile.practical_component_description or "").strip():
            issues.append("Componente prático obrigatório sem descrição")
        if profile.requires_final_assessment and profile.practical_scenario_question_count < 1:
            issues.append("Avaliação online precisa contemplar ao menos uma situação prática")

        configured_fields = set(profile.certificate_required_fields or [])
        missing_cert_fields = sorted(NR1_CERTIFICATE_FIELDS - configured_fields)
        if missing_cert_fields:
            issues.append("Campos obrigatórios do certificado ausentes: " + ", ".join(missing_cert_fields))

        project = None
        if profile.pedagogical_project_version_id:
            project = (
                await db.execute(
                    select(PedagogicalProjectVersion).where(
                        PedagogicalProjectVersion.id == profile.pedagogical_project_version_id,
                        PedagogicalProjectVersion.tenant_id == tenant_id,
                        PedagogicalProjectVersion.course_id == course_id,
                    )
                )
            ).scalar_one_or_none()
        if not project:
            issues.append("Projeto Pedagógico versionado não vinculado")
        else:
            if project.status != PedagogicalProjectStatus.APPROVED.value:
                issues.append("Projeto Pedagógico ainda não aprovado")
            if project.valid_until and project.valid_until < date.today():
                issues.append("Projeto Pedagógico está vencido e precisa ser revisto")
            if not project.theoretical_program:
                issues.append("Conteúdo programático teórico não informado")
            if profile.requires_practical_component and not project.practical_program:
                issues.append("Conteúdo programático prático não informado")
            if not project.module_objectives:
                issues.append("Objetivos dos módulos não informados")
            if project.workload_hours <= 0:
                issues.append("Carga horária do Projeto Pedagógico inválida")
            if project.minimum_daily_dedication_minutes <= 0:
                issues.append("Dedicação diária mínima não definida")
            if project.maximum_completion_days <= 0:
                issues.append("Prazo máximo para conclusão não definido")

        technical = None
        if profile.technical_responsible_id:
            technical = (
                await db.execute(
                    select(TrainingProfessional).where(
                        TrainingProfessional.id == profile.technical_responsible_id,
                        TrainingProfessional.tenant_id == tenant_id,
                        TrainingProfessional.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
        if not technical:
            issues.append("Responsável técnico ativo não vinculado")
        else:
            if not technical.qualification.strip():
                issues.append("Qualificação do responsável técnico não informada")
            if not technical.signature_method or not technical.signature_reference:
                issues.append("Assinatura do responsável técnico não configurada")
            if technical.signature_verified_at is None:
                issues.append("Assinatura do responsável técnico ainda não verificada")

        if project:
            instructor_count = await db.scalar(
                select(func.count(CourseProfessionalAssignment.id)).where(
                    CourseProfessionalAssignment.tenant_id == tenant_id,
                    CourseProfessionalAssignment.course_id == course_id,
                    CourseProfessionalAssignment.pedagogical_project_version_id == project.id,
                    CourseProfessionalAssignment.role == ProfessionalRole.INSTRUCTOR.value,
                )
            )
            if not instructor_count:
                issues.append("Nenhum instrutor vinculado ao Projeto Pedagógico")

        if profile.next_compliance_review_at and profile.next_compliance_review_at <= utc_now():
            issues.append("Revisão regulatória vencida")

        return ComplianceReadiness(not issues, issues)

    @staticmethod
    async def approve_profile(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        course_id: UUID,
        approving_professional_id: UUID,
    ) -> CourseComplianceProfile:
        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == tenant_id,
                    CourseComplianceProfile.course_id == course_id,
                )
            )
        ).scalar_one()
        if profile.technical_responsible_id != approving_professional_id:
            raise ValueError("Somente o responsável técnico vinculado pode aprovar a conformidade")
        readiness = await ComplianceService.readiness(db, tenant_id=tenant_id, course_id=course_id)
        if not readiness.ready:
            raise ValueError("; ".join(readiness.issues))
        now = utc_now()
        profile.status = ComplianceStatus.COMPLIANCE_READY.value
        profile.approved_at = now
        profile.approved_by_professional_id = approving_professional_id
        profile.last_compliance_review_at = now
        profile.next_compliance_review_at = now + timedelta(days=730)
        profile.official_issuance_enabled = True
        return profile

    @staticmethod
    async def official_issuance_readiness(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        enrollment: Enrollment,
        course_id: UUID,
        student_id: UUID,
    ) -> ComplianceReadiness:
        base = await ComplianceService.readiness(db, tenant_id=tenant_id, course_id=course_id)
        issues = list(base.issues)
        profile = (
            await db.execute(
                select(CourseComplianceProfile).where(
                    CourseComplianceProfile.tenant_id == tenant_id,
                    CourseComplianceProfile.course_id == course_id,
                )
            )
        ).scalar_one_or_none()
        if not profile or profile.status != ComplianceStatus.COMPLIANCE_READY.value or not profile.official_issuance_enabled:
            issues.append("Emissão oficial não habilitada pelo responsável técnico")
            return ComplianceReadiness(False, list(dict.fromkeys(issues)))

        required_total = await db.scalar(
            select(func.count(Lesson.id)).where(
                Lesson.tenant_id == tenant_id,
                Lesson.course_id == course_id,
                Lesson.is_required.is_(True),
            )
        ) or 0
        completed_total = await db.scalar(
            select(func.count(LessonProgress.id))
            .join(Lesson, LessonProgress.lesson_id == Lesson.id)
            .where(
                LessonProgress.tenant_id == tenant_id,
                LessonProgress.student_id == student_id,
                Lesson.course_id == course_id,
                Lesson.is_required.is_(True),
                LessonProgress.completed.is_(True),
            )
        ) or 0
        if not required_total or completed_total < required_total:
            issues.append("Aulas obrigatórias ainda não concluídas")

        if profile.requires_final_assessment:
            passed = (
                await db.execute(
                    select(AssessmentAttempt).where(
                        AssessmentAttempt.tenant_id == tenant_id,
                        AssessmentAttempt.enrollment_id == enrollment.id,
                        AssessmentAttempt.student_id == student_id,
                        AssessmentAttempt.course_id == course_id,
                        AssessmentAttempt.passed.is_(True),
                        AssessmentAttempt.completed_at.is_not(None),
                    )
                )
            ).scalar_one_or_none()
            if not passed:
                issues.append("Avaliação de aprendizagem ainda não satisfatória")

        signature = (
            await db.execute(
                select(StudentSignatureEvidence).where(
                    StudentSignatureEvidence.tenant_id == tenant_id,
                    StudentSignatureEvidence.enrollment_id == enrollment.id,
                    StudentSignatureEvidence.student_id == student_id,
                )
            )
        ).scalar_one_or_none()
        if not signature:
            issues.append("Confirmação eletrônica do trabalhador não registrada")

        if profile.requires_practical_component:
            practical = (
                await db.execute(
                    select(PracticalCompletionEvidence).where(
                        PracticalCompletionEvidence.tenant_id == tenant_id,
                        PracticalCompletionEvidence.enrollment_id == enrollment.id,
                        PracticalCompletionEvidence.student_id == student_id,
                        PracticalCompletionEvidence.course_id == course_id,
                        PracticalCompletionEvidence.result == "SATISFATORIO",
                    )
                )
            ).scalar_one_or_none()
            if not practical:
                issues.append("Componente prático obrigatório ainda não satisfatório")

        return ComplianceReadiness(not issues, list(dict.fromkeys(issues)))

    @staticmethod
    async def log_event(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        course_id: UUID,
        event_type: str,
        enrollment_id: UUID | None = None,
        lesson_id: UUID | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
        retention_until: date | None = None,
    ) -> TrainingAccessLog:
        log = TrainingAccessLog(
            tenant_id=tenant_id,
            student_id=student_id,
            enrollment_id=enrollment_id,
            course_id=course_id,
            lesson_id=lesson_id,
            event_type=event_type,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
            event_metadata=metadata,
            retention_until=retention_until,
        )
        db.add(log)
        return log
