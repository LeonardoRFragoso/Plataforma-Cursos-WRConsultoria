"""Add Certificate Studio versioned templates.

Revision ID: h6c7d8e9f0a1
Revises: g5b6c7d8e9f0
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h6c7d8e9f0a1"
down_revision: Union[str, None] = "g5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table}
        ON {table} FOR ALL TO public
        USING (
            current_setting('app.bypass_rls', true) = '1'
            OR tenant_id = current_setting('app.current_tenant', true)::UUID
        )
        WITH CHECK (
            current_setting('app.bypass_rls', true) = '1'
            OR tenant_id = current_setting('app.current_tenant', true)::UUID
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "certificate_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_certificate_template_tenant_slug"),
    )
    op.create_index("ix_certificate_templates_tenant_id", "certificate_templates", ["tenant_id"])
    op.create_index("ix_certificate_templates_slug", "certificate_templates", ["slug"])
    op.create_index("ix_certificate_templates_is_active", "certificate_templates", ["is_active"])
    op.create_index("ix_certificate_templates_tenant_active", "certificate_templates", ["tenant_id", "is_active"])

    op.create_table(
        "certificate_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("visual_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "template_id", "version", name="uq_certificate_template_version_number"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED')", name="ck_certificate_template_version_status"),
    )
    for column in ("tenant_id", "template_id", "status"):
        op.create_index(f"ix_certificate_template_versions_{column}", "certificate_template_versions", [column])
    op.create_index(
        "ix_certificate_template_versions_tenant_template_status",
        "certificate_template_versions",
        ["tenant_id", "template_id", "status"],
    )

    op.create_table(
        "course_certificate_template_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "course_id", name="uq_course_certificate_template_assignment"),
    )
    for column in ("tenant_id", "course_id", "template_id"):
        op.create_index(f"ix_course_certificate_template_assignments_{column}", "course_certificate_template_assignments", [column])
    op.create_index(
        "ix_course_certificate_template_tenant_template",
        "course_certificate_template_assignments",
        ["tenant_id", "template_id"],
    )

    for table in (
        "certificate_templates",
        "certificate_template_versions",
        "course_certificate_template_assignments",
    ):
        _enable_rls(table)

    # Published versions are immutable. Drafts may change, and publication is
    # a one-way transition that must record who/when published it.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_certificate_template_version_immutability()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'certificate template versions are immutable records';
            END IF;
            IF OLD.status = 'PUBLISHED' THEN
                RAISE EXCEPTION 'published certificate template versions are immutable';
            END IF;
            IF NEW.status = 'PUBLISHED' THEN
                IF NEW.published_at IS NULL OR NEW.published_by IS NULL THEN
                    RAISE EXCEPTION 'published certificate template version requires publication evidence';
                END IF;
            ELSIF NEW.published_at IS NOT NULL OR NEW.published_by IS NOT NULL THEN
                RAISE EXCEPTION 'draft certificate template cannot have publication evidence';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_certificate_template_version_immutable
        BEFORE UPDATE OR DELETE ON certificate_template_versions
        FOR EACH ROW EXECUTE FUNCTION protect_certificate_template_version_immutability()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_certificate_template_version_immutable ON certificate_template_versions")
    op.execute("DROP FUNCTION IF EXISTS protect_certificate_template_version_immutability()")
    for table in (
        "course_certificate_template_assignments",
        "certificate_template_versions",
        "certificate_templates",
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("course_certificate_template_assignments")
    op.drop_table("certificate_template_versions")
    op.drop_table("certificate_templates")
