"""Add versioned compliance retention governance.

Revision ID: i7c8d9e0f1a2
Revises: h6c7d8e9f0a1
Create Date: 2026-08-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "i7c8d9e0f1a2"
down_revision: str | None = "h6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Idempotent: handles partially-applied states from crashed deployments."""
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "compliance_retention_policy_versions"):
        op.create_table(
            "compliance_retention_policy_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
            sa.Column("certificate_retention_days", sa.Integer(), nullable=True),
            sa.Column("assessment_retention_days", sa.Integer(), nullable=True),
            sa.Column("training_event_retention_days", sa.Integer(), nullable=True),
            sa.Column("student_confirmation_retention_days", sa.Integer(), nullable=True),
            sa.Column("practical_evidence_retention_days", sa.Integer(), nullable=True),
            sa.Column("legal_basis", sa.Text(), nullable=True),
            sa.Column("purpose", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "version", name="uq_compliance_retention_policy_version"),
            sa.CheckConstraint("status IN ('DRAFT','APPROVED')", name="ck_compliance_retention_policy_status"),
            sa.CheckConstraint(
                "certificate_retention_days IS NULL OR certificate_retention_days > 0",
                name="ck_compliance_retention_certificate_days",
            ),
            sa.CheckConstraint(
                "assessment_retention_days IS NULL OR assessment_retention_days > 0",
                name="ck_compliance_retention_assessment_days",
            ),
            sa.CheckConstraint(
                "training_event_retention_days IS NULL OR training_event_retention_days > 0",
                name="ck_compliance_retention_training_days",
            ),
            sa.CheckConstraint(
                "student_confirmation_retention_days IS NULL OR student_confirmation_retention_days > 0",
                name="ck_compliance_retention_confirmation_days",
            ),
            sa.CheckConstraint(
                "practical_evidence_retention_days IS NULL OR practical_evidence_retention_days > 0",
                name="ck_compliance_retention_practical_days",
            ),
        )
        op.create_index(
            "ix_compliance_retention_policy_versions_tenant_id",
            "compliance_retention_policy_versions",
            ["tenant_id"],
        )
        op.create_index(
            "ix_compliance_retention_policy_versions_status",
            "compliance_retention_policy_versions",
            ["status"],
        )
        op.create_index(
            "ix_compliance_retention_tenant_status",
            "compliance_retention_policy_versions",
            ["tenant_id", "status"],
        )

    op.execute("ALTER TABLE compliance_retention_policy_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE compliance_retention_policy_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_compliance_retention_policy_versions "
        "ON compliance_retention_policy_versions"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_compliance_retention_policy_versions
        ON compliance_retention_policy_versions FOR ALL TO public
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

    # Approved governance versions are immutable and cannot be deleted. Drafts
    # may be edited, but approval is one-way and must include all legal inputs.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_compliance_retention_policy_version()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'compliance retention policy versions are immutable records';
            END IF;
            IF OLD.status = 'APPROVED' THEN
                RAISE EXCEPTION 'approved compliance retention policy versions are immutable';
            END IF;
            IF NEW.status = 'APPROVED' THEN
                IF NEW.approved_at IS NULL OR NEW.approved_by IS NULL THEN
                    RAISE EXCEPTION 'approved retention policy requires approval evidence';
                END IF;
                IF NEW.legal_basis IS NULL OR btrim(NEW.legal_basis) = '' THEN
                    RAISE EXCEPTION 'approved retention policy requires legal basis';
                END IF;
                IF NEW.purpose IS NULL OR btrim(NEW.purpose) = '' THEN
                    RAISE EXCEPTION 'approved retention policy requires purpose';
                END IF;
                IF NEW.certificate_retention_days IS NULL
                   OR NEW.assessment_retention_days IS NULL
                   OR NEW.training_event_retention_days IS NULL
                   OR NEW.student_confirmation_retention_days IS NULL
                   OR NEW.practical_evidence_retention_days IS NULL THEN
                    RAISE EXCEPTION 'approved retention policy requires all retention periods';
                END IF;
            ELSIF NEW.approved_at IS NOT NULL OR NEW.approved_by IS NOT NULL THEN
                RAISE EXCEPTION 'draft retention policy cannot have approval evidence';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_compliance_retention_policy_immutable "
        "ON compliance_retention_policy_versions"
    )
    op.execute(
        """
        CREATE TRIGGER trg_compliance_retention_policy_immutable
        BEFORE UPDATE OR DELETE ON compliance_retention_policy_versions
        FOR EACH ROW EXECUTE FUNCTION protect_compliance_retention_policy_version()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_compliance_retention_policy_immutable "
        "ON compliance_retention_policy_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_compliance_retention_policy_version()")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_compliance_retention_policy_versions "
        "ON compliance_retention_policy_versions"
    )
    op.execute("ALTER TABLE compliance_retention_policy_versions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE compliance_retention_policy_versions DISABLE ROW LEVEL SECURITY")
    op.drop_table("compliance_retention_policy_versions")
