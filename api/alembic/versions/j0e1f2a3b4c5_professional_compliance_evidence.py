"""Add auditable professional compliance evidence.

Revision ID: j0e1f2a3b4c5
Revises: 3f273adccf42
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "j0e1f2a3b4c5"
down_revision: str | None = "3f273adccf42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "training_professional_evidence"):
        op.create_table(
            "training_professional_evidence",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "professional_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("training_professionals.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("document_reference", sa.String(length=1024), nullable=True),
            sa.Column("document_sha256", sa.String(length=64), nullable=True),
            sa.Column("issuer", sa.String(length=255), nullable=True),
            sa.Column("reference_number", sa.String(length=255), nullable=True),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column(
                "verified_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "evidence_type IN ('LEGAL_QUALIFICATION','PROFESSIONAL_REGISTRATION','PROFICIENCY','EXPERIENCE','TRAINING_CERTIFICATE','OTHER')",
                name="ck_training_professional_evidence_type",
            ),
            sa.CheckConstraint(
                "status IN ('PENDING','VERIFIED','REJECTED')",
                name="ck_training_professional_evidence_status",
            ),
            sa.CheckConstraint(
                "document_sha256 IS NULL OR document_sha256 ~ '^[0-9a-f]{64}$'",
                name="ck_training_professional_evidence_sha256",
            ),
        )
        op.create_index(
            "ix_training_professional_evidence_tenant_id",
            "training_professional_evidence",
            ["tenant_id"],
        )
        op.create_index(
            "ix_training_professional_evidence_professional_id",
            "training_professional_evidence",
            ["professional_id"],
        )
        op.create_index(
            "ix_training_professional_evidence_status",
            "training_professional_evidence",
            ["status"],
        )
        op.create_index(
            "ix_training_professional_evidence_expires_at",
            "training_professional_evidence",
            ["expires_at"],
        )
        op.create_index(
            "ix_training_professional_evidence_tenant_professional",
            "training_professional_evidence",
            ["tenant_id", "professional_id"],
        )
        op.create_index(
            "ix_training_professional_evidence_tenant_type_status",
            "training_professional_evidence",
            ["tenant_id", "evidence_type", "status"],
        )

    op.execute("ALTER TABLE training_professional_evidence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE training_professional_evidence FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_training_professional_evidence "
        "ON training_professional_evidence"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_training_professional_evidence
        ON training_professional_evidence FOR ALL TO public
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


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_training_professional_evidence "
        "ON training_professional_evidence"
    )
    op.execute("ALTER TABLE training_professional_evidence NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE training_professional_evidence DISABLE ROW LEVEL SECURITY")
    op.drop_table("training_professional_evidence")
