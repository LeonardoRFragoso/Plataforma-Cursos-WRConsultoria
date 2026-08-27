"""Add certificate signing orchestration.

Revision ID: g5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g5b6c7d8e9f0"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
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
        "certificate_signing_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="DISABLED"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signer_display_name", sa.String(length=255), nullable=False),
        sa.Column("signer_identifier", sa.String(length=128), nullable=True),
        sa.Column("certificate_fingerprint_sha256", sa.String(length=64), nullable=True),
        sa.Column("certificate_serial", sa.String(length=256), nullable=True),
        sa.Column("certificate_subject", sa.Text(), nullable=True),
        sa.Column("certificate_issuer", sa.Text(), nullable=True),
        sa.Column("certificate_not_before", sa.DateTime(), nullable=True),
        sa.Column("certificate_not_after", sa.DateTime(), nullable=True),
        sa.Column("key_reference", sa.String(length=512), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", name="uq_certificate_signing_profile_tenant"),
        sa.CheckConstraint(
            "certificate_fingerprint_sha256 IS NULL OR length(certificate_fingerprint_sha256) = 64",
            name="ck_certificate_signing_profile_fingerprint",
        ),
    )
    op.create_index("ix_certificate_signing_profiles_tenant_id", "certificate_signing_profiles", ["tenant_id"])
    op.create_index("ix_certificate_signing_profiles_certificate_fingerprint_sha256", "certificate_signing_profiles", ["certificate_fingerprint_sha256"])
    op.create_index("ix_certificate_signing_profiles_certificate_not_after", "certificate_signing_profiles", ["certificate_not_after"])
    op.create_index("ix_certificate_signing_profiles_tenant_enabled", "certificate_signing_profiles", ["tenant_id", "enabled"])

    op.create_table(
        "certificate_signing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_signing_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("provider_job_id", sa.String(length=512), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("result_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "document_id", name="uq_certificate_signing_job_tenant_document"),
        sa.CheckConstraint(
            "status IN ('QUEUED','SUBMITTING','WAITING_PROVIDER','RETRY_SCHEDULED','SIGNED','FAILED','CANCELLED')",
            name="ck_certificate_signing_job_status",
        ),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="ck_certificate_signing_job_attempts"),
    )
    for column in ("tenant_id", "document_id", "certificate_id", "profile_id", "provider", "status", "next_attempt_at"):
        op.create_index(f"ix_certificate_signing_jobs_{column}", "certificate_signing_jobs", [column])
    op.create_index("ix_certificate_signing_jobs_tenant_status_next", "certificate_signing_jobs", ["tenant_id", "status", "next_attempt_at"])
    op.create_index("ix_certificate_signing_jobs_provider_job", "certificate_signing_jobs", ["provider", "provider_job_id"])

    op.create_table(
        "certificate_signing_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_signing_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("tenant_id", "job_id", "event_type"):
        op.create_index(f"ix_certificate_signing_events_{column}", "certificate_signing_events", [column])
    op.create_index("ix_certificate_signing_events_tenant_job_created", "certificate_signing_events", ["tenant_id", "job_id", "created_at"])

    for table in ("certificate_signing_profiles", "certificate_signing_jobs", "certificate_signing_events"):
        _enable_rls(table)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_certificate_signing_event_immutability()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'certificate_signing_events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_certificate_signing_events_append_only
        BEFORE UPDATE OR DELETE ON certificate_signing_events
        FOR EACH ROW EXECUTE FUNCTION protect_certificate_signing_event_immutability()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_certificate_signing_events_append_only ON certificate_signing_events")
    op.execute("DROP FUNCTION IF EXISTS protect_certificate_signing_event_immutability()")
    for table in ("certificate_signing_events", "certificate_signing_jobs", "certificate_signing_profiles"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("certificate_signing_events")
    op.drop_table("certificate_signing_jobs")
    op.drop_table("certificate_signing_profiles")
