"""P0 NR-1 compliance foundation and immutable certificate evidence.

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f5
Create Date: 2026-08-27

Adds the regulatory data that must be known before an NR course can be
marked COMPLIANCE_READY. The migration is intentionally fail-closed: it does
not populate or invent professional qualifications, regulatory decisions or
signatures for existing courses.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (current_setting('app.bypass_rls', true) = '1' OR "
        f"tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' OR "
        f"tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.create_table(
        "training_professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("qualification", sa.Text(), nullable=False),
        sa.Column("professional_council", sa.String(), nullable=True),
        sa.Column("registration_number", sa.String(), nullable=True),
        sa.Column("registration_state", sa.String(length=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("signature_method", sa.String(), nullable=True),
        sa.Column("signature_reference", sa.String(), nullable=True),
        sa.Column("signature_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
    )
    op.create_index("ix_training_professionals_tenant_id", "training_professionals", ["tenant_id"])

    op.create_table(
        "pedagogical_project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("general_objective", sa.Text(), nullable=False),
        sa.Column("principles_and_concepts", sa.Text(), nullable=False),
        sa.Column("pedagogical_strategy", sa.Text(), nullable=False),
        sa.Column("support_infrastructure", sa.Text(), nullable=False),
        sa.Column("theoretical_program", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("practical_program", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("module_objectives", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("workload_hours", sa.Integer(), nullable=False),
        sa.Column("minimum_daily_dedication_minutes", sa.Integer(), nullable=False),
        sa.Column("maximum_completion_days", sa.Integer(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("didactic_materials", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("learning_tools", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assessment_methodology", sa.Text(), nullable=False),
        sa.Column("practical_strategy", sa.Text(), nullable=True),
        sa.Column("normative_reference", sa.Text(), nullable=False),
        sa.Column("technical_responsible_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "course_id", "version", name="uq_pedagogical_project_course_version"),
    )
    op.create_index("ix_pedagogical_project_versions_tenant_id", "pedagogical_project_versions", ["tenant_id"])
    op.create_index("ix_pedagogical_project_versions_course_id", "pedagogical_project_versions", ["course_id"])

    op.create_table(
        "course_professional_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("pedagogical_project_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pedagogical_project_versions.id"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "course_id", "pedagogical_project_version_id", "professional_id", "role",
            name="uq_course_professional_assignment",
        ),
    )
    op.create_index("ix_course_professional_assignments_tenant_id", "course_professional_assignments", ["tenant_id"])
    op.create_index("ix_course_professional_assignments_course_id", "course_professional_assignments", ["course_id"])
    op.create_index("ix_course_professional_assignments_project_id", "course_professional_assignments", ["pedagogical_project_version_id"])
    op.create_index("ix_course_professional_assignments_professional_id", "course_professional_assignments", ["professional_id"])
    op.create_index("ix_course_professional_assignments_role", "course_professional_assignments", ["role"])

    op.create_table(
        "course_compliance_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("regulatory_standard", sa.String(), nullable=False),
        sa.Column("regulatory_version", sa.String(), nullable=False),
        sa.Column("regulatory_source_url", sa.Text(), nullable=False),
        sa.Column("regulatory_effective_from", sa.Date(), nullable=True),
        sa.Column("delivery_mode", sa.String(), nullable=False),
        sa.Column("requires_practical_component", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("practical_component_description", sa.Text(), nullable=True),
        sa.Column("requires_final_assessment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("minimum_score", sa.Float(), nullable=False, server_default="60"),
        sa.Column("validity_period_months", sa.Integer(), nullable=True),
        sa.Column("recycling_rule", sa.Text(), nullable=True),
        sa.Column("regulatory_prerequisites", sa.Text(), nullable=True),
        sa.Column("certificate_required_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("practical_scenario_question_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("access_log_retention_months_after_validity", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("pedagogical_project_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pedagogical_project_versions.id"), nullable=True),
        sa.Column("technical_responsible_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=True),
        sa.Column("last_compliance_review_at", sa.DateTime(), nullable=True),
        sa.Column("next_compliance_review_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=True),
        sa.Column("official_issuance_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_profile"),
    )
    op.create_index("ix_course_compliance_profiles_tenant_id", "course_compliance_profiles", ["tenant_id"])
    op.create_index("ix_course_compliance_profiles_course_id", "course_compliance_profiles", ["course_id"])
    op.create_index("ix_course_compliance_profiles_project_id", "course_compliance_profiles", ["pedagogical_project_version_id"])
    op.create_index("ix_course_compliance_profiles_rt_id", "course_compliance_profiles", ["technical_responsible_id"])
    op.create_index("ix_course_compliance_profiles_status", "course_compliance_profiles", ["status"])

    op.create_table(
        "practical_completion_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id"), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for col in ("tenant_id", "enrollment_id", "student_id", "course_id", "result"):
        op.create_index(f"ix_practical_completion_evidence_{col}", "practical_completion_evidence", [col])

    op.create_table(
        "training_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("retention_until", sa.Date(), nullable=True),
    )
    for col in ("tenant_id", "student_id", "enrollment_id", "course_id", "lesson_id", "event_type", "occurred_at", "retention_until"):
        op.create_index(f"ix_training_access_logs_{col}", "training_access_logs", [col])

    op.add_column(
        "classes",
        sa.Column("pedagogical_project_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_classes_pedagogical_project_version",
        "classes", "pedagogical_project_versions",
        ["pedagogical_project_version_id"], ["id"],
    )
    op.create_index("ix_classes_pedagogical_project_version_id", "classes", ["pedagogical_project_version_id"])

    # Keep ORM/database defaults aligned with the current WR assessment policy.
    op.alter_column("assessment_attempts", "minimum_score", server_default="60", existing_type=sa.Float())
    for name, typ in (
        ("declaration_text_hash", sa.String(length=64)),
        ("certification_payload_hash", sa.String(length=64)),
        ("session_id", sa.String(length=128)),
        ("ip_address", sa.String(length=64)),
        ("user_agent", sa.String(length=512)),
    ):
        op.add_column("student_signature_evidence", sa.Column(name, typ, nullable=True))

    op.add_column("certificates", sa.Column("snapshot_json", postgresql.JSONB(), nullable=True))
    op.add_column("certificates", sa.Column("pdf_storage_key", sa.String(), nullable=True))
    op.add_column("certificates", sa.Column("pdf_sha256", sa.String(length=64), nullable=True))
    op.add_column("certificates", sa.Column("pdf_generated_at", sa.DateTime(), nullable=True))
    op.add_column("certificates", sa.Column("signature_status", sa.String(), nullable=False, server_default="NOT_REQUIRED"))
    op.add_column("certificates", sa.Column("signature_method", sa.String(), nullable=True))
    op.add_column("certificates", sa.Column("signature_fingerprint", sa.String(), nullable=True))
    op.add_column("certificates", sa.Column("signed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_certificates_pdf_sha256", "certificates", ["pdf_sha256"])
    op.create_index("ix_certificates_signature_status", "certificates", ["signature_status"])

    for table in (
        "training_professionals",
        "pedagogical_project_versions",
        "course_professional_assignments",
        "course_compliance_profiles",
        "practical_completion_evidence",
        "training_access_logs",
    ):
        _enable_rls(table)


def downgrade() -> None:
    for table in (
        "training_access_logs",
        "practical_completion_evidence",
        "course_compliance_profiles",
        "course_professional_assignments",
        "pedagogical_project_versions",
        "training_professionals",
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_certificates_signature_status", table_name="certificates")
    op.drop_index("ix_certificates_pdf_sha256", table_name="certificates")
    for name in (
        "signed_at", "signature_fingerprint", "signature_method", "signature_status",
        "pdf_generated_at", "pdf_sha256", "pdf_storage_key", "snapshot_json",
    ):
        op.drop_column("certificates", name)

    for name in ("user_agent", "ip_address", "session_id", "certification_payload_hash", "declaration_text_hash"):
        op.drop_column("student_signature_evidence", name)
    op.alter_column("assessment_attempts", "minimum_score", server_default="70", existing_type=sa.Float())

    op.drop_index("ix_classes_pedagogical_project_version_id", table_name="classes")
    op.drop_constraint("fk_classes_pedagogical_project_version", "classes", type_="foreignkey")
    op.drop_column("classes", "pedagogical_project_version_id")

    op.drop_table("training_access_logs")
    op.drop_table("practical_completion_evidence")
    op.drop_table("course_compliance_profiles")
    op.drop_table("course_professional_assignments")
    op.drop_table("pedagogical_project_versions")
    op.drop_table("training_professionals")
