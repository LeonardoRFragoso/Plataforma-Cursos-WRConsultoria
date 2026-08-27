"""P0 NR compliance foundation and fail-closed regulatory profiles.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-08-27

No course is marked COMPLIANCE_READY by this migration. Known regulatory
facts are pre-populated only where confirmed from current official MTE text;
all remaining business/technical facts require explicit human review.
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_columns():
    return []


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'''CREATE POLICY tenant_isolation_{table} ON "{table}"
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                OR current_setting('app.bypass_rls', true) = '1'
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                OR current_setting('app.bypass_rls', true) = '1'
            )'''
        )
    )


def upgrade() -> None:
    op.create_table(
        "training_professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("cpf", sa.String(), nullable=True),
        sa.Column("professional_role", sa.String(), nullable=False),
        sa.Column("qualification", sa.Text(), nullable=False),
        sa.Column("professional_council", sa.String(), nullable=True),
        sa.Column("registration_number", sa.String(), nullable=True),
        sa.Column("proficiency_evidence", sa.Text(), nullable=True),
        sa.Column("signature_method", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
    )
    op.create_index("ix_training_professionals_tenant_id", "training_professionals", ["tenant_id"])

    op.create_table(
        "pedagogical_project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("general_objective", sa.Text(), nullable=True),
        sa.Column("safety_principles", sa.Text(), nullable=True),
        sa.Column("pedagogical_strategy", sa.Text(), nullable=True),
        sa.Column("operational_infrastructure", sa.Text(), nullable=True),
        sa.Column("theoretical_program", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("practical_program", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("module_objectives", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("workload_hours", sa.Float(), nullable=True),
        sa.Column("minimum_daily_dedication_minutes", sa.Integer(), nullable=True),
        sa.Column("maximum_completion_days", sa.Integer(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("teaching_materials", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("learning_tools", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("assessment_methodology", sa.Text(), nullable=True),
        sa.Column("support_channel", sa.Text(), nullable=True),
        sa.Column("normative_reference", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "course_id", "version", name="uq_pedagogical_project_course_version"),
    )
    op.create_index("ix_pedagogical_project_versions_tenant_id", "pedagogical_project_versions", ["tenant_id"])
    op.create_index("ix_pedagogical_project_versions_course_id", "pedagogical_project_versions", ["course_id"])

    op.create_table(
        "course_compliance_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("regulatory_standard", sa.String(), nullable=True),
        sa.Column("regulatory_version", sa.Text(), nullable=True),
        sa.Column("normative_source_url", sa.Text(), nullable=True),
        sa.Column("source_checked_at", sa.DateTime(), nullable=True),
        sa.Column("required_delivery_mode", sa.String(), nullable=True),
        sa.Column("requires_practical_component", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("practical_minimum_percent", sa.Float(), nullable=True),
        sa.Column("requires_final_assessment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assessment_practical_scenarios_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimum_score", sa.Float(), nullable=True),
        sa.Column("minimum_workload_hours", sa.Float(), nullable=True),
        sa.Column("periodicity_months", sa.Integer(), nullable=True),
        sa.Column("prerequisites", sa.Text(), nullable=True),
        sa.Column("technical_responsible_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=True),
        sa.Column("pedagogical_project_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pedagogical_project_versions.id"), nullable=True),
        sa.Column("support_channel_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("next_review_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_tenant_course"),
    )
    op.create_index("ix_course_compliance_profiles_tenant_id", "course_compliance_profiles", ["tenant_id"])
    op.create_index("ix_course_compliance_profiles_course_id", "course_compliance_profiles", ["course_id"])
    op.create_index("ix_course_compliance_profiles_regulatory_standard", "course_compliance_profiles", ["regulatory_standard"])
    op.create_index("ix_course_compliance_profiles_status", "course_compliance_profiles", ["status"])

    op.create_table(
        "course_training_professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "course_id", "professional_id", "role", name="uq_course_training_professional"),
    )
    op.create_index("ix_course_training_professionals_tenant_id", "course_training_professionals", ["tenant_id"])
    op.create_index("ix_course_training_professionals_course_id", "course_training_professionals", ["course_id"])

    op.create_table(
        "practical_training_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("practical_percent", sa.Float(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("tenant_id", "enrollment_id", "course_id", "student_id"):
        op.create_index(f"ix_practical_training_records_{col}", "practical_training_records", [col])

    op.create_table(
        "training_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("active_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("tenant_id", "enrollment_id", "student_id", "course_id"):
        op.create_index(f"ix_training_sessions_{col}", "training_sessions", [col])

    op.create_table(
        "training_access_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_sessions.id"), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("retain_until", sa.DateTime(), nullable=True),
    )
    for col in ("tenant_id", "enrollment_id", "student_id", "course_id", "lesson_id", "event_type", "occurred_at", "retain_until"):
        op.create_index(f"ix_training_access_events_{col}", "training_access_events", [col])

    # Strengthen the existing electronic-confirmation evidence without ever storing a password.
    op.add_column("student_signature_evidence", sa.Column("declaration_text_hash", sa.String(), nullable=True))
    op.add_column("student_signature_evidence", sa.Column("evidence_payload_hash", sa.String(), nullable=True))
    op.add_column("student_signature_evidence", sa.Column("ip_address", sa.String(), nullable=True))
    op.add_column("student_signature_evidence", sa.Column("user_agent", sa.Text(), nullable=True))

    for table in (
        "training_professionals",
        "pedagogical_project_versions",
        "course_compliance_profiles",
        "course_training_professionals",
        "practical_training_records",
        "training_sessions",
        "training_access_events",
    ):
        _enable_rls(table)

    # Seed fail-closed compliance profiles. No human/CEO fact is fabricated and
    # no row is approved automatically.
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = bind.execute(
        sa.text("SELECT id, tenant_id, code FROM courses WHERE is_active = true")
    ).mappings().all()
    for row in rows:
        code = row["code"] or ""
        if not code.startswith("NR-"):
            continue
        parts = code.split("-")
        standard = "-".join(parts[:2]) if len(parts) >= 2 else code
        values = {
            "id": uuid4(),
            "tenant_id": row["tenant_id"],
            "course_id": row["id"],
            "regulatory_standard": standard,
            "status": "REVIEW_REQUIRED",
            "source_checked_at": None,
            "required_delivery_mode": None,
            "requires_practical_component": False,
            "practical_minimum_percent": None,
            "requires_final_assessment": False,
            "minimum_score": None,
            "minimum_workload_hours": None,
            "periodicity_months": None,
            "blocker_reason": "Revisão normativa e validação do responsável técnico pendentes.",
            "created_at": now,
            "updated_at": now,
        }
        if standard == "NR-35":
            values.update(
                regulatory_version="NR-35 vigente com alteração da Portaria MTE nº 1.259/2026",
                normative_source_url="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/nr-35",
                source_checked_at=now,
                required_delivery_mode="PRESENCIAL",
                requires_practical_component=True,
                requires_final_assessment=True,
                minimum_score=60.0,
                minimum_workload_hours=8.0,
                periodicity_months=24,
                blocker_reason="NR-35 item 35.4.5 exige treinamento presencial; a oferta digital atual permanece somente para homologação/estudo até adequação presencial e validação técnica.",
            )
        elif standard == "NR-33":
            values.update(
                regulatory_version="NR-33 vigente (Portaria MTP nº 1.690/2022)",
                normative_source_url="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/nr-33-atualizada-2022.pdf",
                source_checked_at=now,
                required_delivery_mode="PRESENCIAL",
                requires_practical_component=True,
                practical_minimum_percent=50.0 if code == "NR-33-AUT" else None,
                requires_final_assessment=True,
                minimum_score=60.0,
                minimum_workload_hours=16.0 if code == "NR-33-AUT" else None,
                periodicity_months=12,
                blocker_reason="NR-33 exige capacitação presencial para trabalhador autorizado/vigia/supervisor e avaliação; o curso digital atual não pode gerar certificado oficial sem o componente presencial/prático e validação técnica.",
            )
        elif standard == "NR-06":
            values.update(
                regulatory_version="NR-06 vigente - última modificação Portaria MTE nº 57/2025",
                normative_source_url="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-6-nr-6",
                source_checked_at=now,
                requires_final_assessment=True,
                minimum_score=60.0,
                blocker_reason="A NR-06 exige orientação/treinamento conforme o EPI e a NR-1; modalidade, duração, público e escopo desta oferta precisam ser formalmente definidos pelo responsável técnico.",
            )
        elif standard == "NR-12":
            values.update(
                regulatory_version="NR-12 vigente - última modificação Portaria MTE nº 344/2024",
                normative_source_url="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-12-nr-12",
                source_checked_at=now,
                requires_final_assessment=True,
                minimum_score=60.0,
                blocker_reason="Escopo geral de NR-12 não substitui capacitação específica exigida para determinada máquina/operação; responsável técnico deve validar público, prática, duração e conteúdo antes da certificação oficial.",
            )
        elif standard == "NR-10":
            values.update(
                regulatory_version="NR-10 Portaria SEPRT nº 915/2019 vigente até 31/05/2027; Portaria MTE nº 737/2026 vigência 01/06/2027",
                normative_source_url="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-10-nr-10",
                source_checked_at=now,
                blocker_reason="Conteúdo precisa ser validado contra a NR-10 atualmente vigente e planejado para a nova redação da Portaria MTE nº 737/2026 antes da vigência em 01/06/2027.",
            )

        bind.execute(
            sa.text(
                """
                INSERT INTO course_compliance_profiles (
                    id, tenant_id, course_id, regulatory_standard, regulatory_version,
                    normative_source_url, source_checked_at, required_delivery_mode,
                    requires_practical_component, practical_minimum_percent,
                    requires_final_assessment, assessment_practical_scenarios_validated,
                    minimum_score, minimum_workload_hours, periodicity_months,
                    support_channel_verified, status, blocker_reason, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :course_id, :regulatory_standard, :regulatory_version,
                    :normative_source_url, :source_checked_at, :required_delivery_mode,
                    :requires_practical_component, :practical_minimum_percent,
                    :requires_final_assessment, false,
                    :minimum_score, :minimum_workload_hours, :periodicity_months,
                    false, :status, :blocker_reason, :created_at, :updated_at
                )
                ON CONFLICT (tenant_id, course_id) DO NOTHING
                """
            ),
            values,
        )


def downgrade() -> None:
    op.drop_column("student_signature_evidence", "user_agent")
    op.drop_column("student_signature_evidence", "ip_address")
    op.drop_column("student_signature_evidence", "evidence_payload_hash")
    op.drop_column("student_signature_evidence", "declaration_text_hash")
    for table in (
        "training_access_events",
        "training_sessions",
        "practical_training_records",
        "course_training_professionals",
        "course_compliance_profiles",
        "pedagogical_project_versions",
        "training_professionals",
    ):
        op.drop_table(table)
