"""NR compliance foundation: professionals, pedagogical projects and course profiles.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.create_table(
        "training_professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("qualification", sa.Text(), nullable=False),
        sa.Column("professional_registration", sa.String(length=128), nullable=True),
        sa.Column("council", sa.String(length=64), nullable=True),
        sa.Column("registration_state", sa.String(length=8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
    )
    op.create_index("ix_training_professionals_tenant_id", "training_professionals", ["tenant_id"])
    op.create_index("ix_training_professionals_cpf", "training_professionals", ["cpf"])
    op.create_index("ix_training_professionals_is_active", "training_professionals", ["is_active"])
    op.create_index(
        "ix_training_professionals_tenant_active",
        "training_professionals",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "pedagogical_project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("general_objective", sa.Text(), nullable=False),
        sa.Column("specific_objectives", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("teaching_strategy", sa.Text(), nullable=False),
        sa.Column("syllabus", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("workload_hours", sa.Float(), nullable=False),
        sa.Column("delivery_mode", sa.String(length=32), nullable=False),
        sa.Column("materials", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assessment_methodology", sa.Text(), nullable=False),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "course_id",
            "version",
            name="uq_pedagogical_project_course_version",
        ),
    )
    op.create_index("ix_pedagogical_project_versions_tenant_id", "pedagogical_project_versions", ["tenant_id"])
    op.create_index("ix_pedagogical_project_versions_course_id", "pedagogical_project_versions", ["course_id"])
    op.create_index(
        "ix_pedagogical_projects_tenant_course_status",
        "pedagogical_project_versions",
        ["tenant_id", "course_id", "status"],
    )

    op.create_table(
        "course_compliance_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("regulatory_standard", sa.String(length=64), nullable=False),
        sa.Column("regulatory_version", sa.String(length=128), nullable=False),
        sa.Column("delivery_mode", sa.String(length=32), nullable=False),
        sa.Column("requires_practical_component", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_final_assessment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("minimum_score", sa.Float(), nullable=True),
        sa.Column("validity_period_months", sa.Integer(), nullable=True),
        sa.Column("prerequisites", sa.Text(), nullable=True),
        sa.Column("certificate_required_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "technical_responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_professionals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "pedagogical_project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pedagogical_project_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_compliance_review_at", sa.DateTime(), nullable=True),
        sa.Column("next_compliance_review_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_tenant_course"),
    )
    op.create_index("ix_course_compliance_profiles_tenant_id", "course_compliance_profiles", ["tenant_id"])
    op.create_index("ix_course_compliance_profiles_course_id", "course_compliance_profiles", ["course_id"])
    op.create_index(
        "ix_course_compliance_profiles_technical_responsible_id",
        "course_compliance_profiles",
        ["technical_responsible_id"],
    )
    op.create_index(
        "ix_course_compliance_profiles_pedagogical_project_version_id",
        "course_compliance_profiles",
        ["pedagogical_project_version_id"],
    )
    op.create_index(
        "ix_course_compliance_tenant_status",
        "course_compliance_profiles",
        ["tenant_id", "status"],
    )

    op.create_table(
        "course_training_professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "professional_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_professionals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "course_id",
            "professional_id",
            "role",
            name="uq_course_training_professional_role",
        ),
    )
    op.create_index("ix_course_training_professionals_tenant_id", "course_training_professionals", ["tenant_id"])
    op.create_index("ix_course_training_professionals_course_id", "course_training_professionals", ["course_id"])
    op.create_index("ix_course_training_professionals_professional_id", "course_training_professionals", ["professional_id"])
    op.create_index("ix_course_training_professionals_role", "course_training_professionals", ["role"])
    op.create_index(
        "ix_course_training_professionals_tenant_course",
        "course_training_professionals",
        ["tenant_id", "course_id"],
    )

    op.add_column(
        "classes",
        sa.Column(
            "pedagogical_project_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pedagogical_project_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_classes_pedagogical_project_version_id",
        "classes",
        ["pedagogical_project_version_id"],
    )

    for table in (
        "training_professionals",
        "pedagogical_project_versions",
        "course_compliance_profiles",
        "course_training_professionals",
    ):
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index("ix_classes_pedagogical_project_version_id", table_name="classes")
    op.drop_column("classes", "pedagogical_project_version_id")

    for table in (
        "course_training_professionals",
        "course_compliance_profiles",
        "pedagogical_project_versions",
        "training_professionals",
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("course_training_professionals")
    op.drop_table("course_compliance_profiles")
    op.drop_table("pedagogical_project_versions")
    op.drop_table("training_professionals")
