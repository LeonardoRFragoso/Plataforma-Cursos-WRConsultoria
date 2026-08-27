"""Add trusted certificate document pipeline.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "certificate_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "certificate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("certificates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("enrollments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING_SIGNATURE",
        ),
        sa.Column("snapshot_version", sa.String(length=16), nullable=False, server_default="1"),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_storage_key", sa.String(length=1024), nullable=False),
        sa.Column("original_pdf_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_size_bytes", sa.Integer(), nullable=False),
        sa.Column("rendered_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("signed_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("signed_pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("signed_size_bytes", sa.Integer(), nullable=True),
        sa.Column("signature_provider", sa.String(length=128), nullable=True),
        sa.Column(
            "signature_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("signed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "certificate_id",
            name="uq_certificate_document_tenant_certificate",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_SIGNATURE','SIGNED')",
            name="ck_certificate_document_status",
        ),
        sa.CheckConstraint(
            "length(snapshot_sha256) = 64 AND length(original_pdf_sha256) = 64",
            name="ck_certificate_document_hash_lengths",
        ),
        sa.CheckConstraint(
            "original_size_bytes > 0",
            name="ck_certificate_document_original_size",
        ),
        sa.CheckConstraint(
            "signed_size_bytes IS NULL OR signed_size_bytes > 0",
            name="ck_certificate_document_signed_size",
        ),
        sa.CheckConstraint(
            "signed_pdf_sha256 IS NULL OR length(signed_pdf_sha256) = 64",
            name="ck_certificate_document_signed_hash_length",
        ),
    )

    for column in (
        "tenant_id",
        "certificate_id",
        "enrollment_id",
        "status",
        "snapshot_sha256",
        "original_pdf_sha256",
        "signed_pdf_sha256",
    ):
        op.create_index(
            f"ix_certificate_documents_{column}",
            "certificate_documents",
            [column],
        )
    op.create_index(
        "ix_certificate_documents_tenant_status",
        "certificate_documents",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_certificate_documents_tenant_enrollment",
        "certificate_documents",
        ["tenant_id", "enrollment_id"],
    )

    # A regulated enrollment may have only one not-yet-signed certificate at
    # a time. The enrollment row is also locked by the application, while this
    # partial unique index closes the remaining database-level race window.
    op.create_index(
        "uq_certificate_pending_signature_per_enrollment",
        "certificates",
        ["enrollment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING_SIGNATURE'"),
    )

    op.execute("ALTER TABLE certificate_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE certificate_documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_certificate_documents
        ON certificate_documents FOR ALL TO public
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

    # The snapshot and original PDF metadata are frozen at INSERT time. The
    # only permitted UPDATE is the one-way transition to SIGNED, filling the
    # signed-artifact fields. Once signed, the row is fully immutable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_certificate_document_immutability()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'certificate_documents cannot be deleted';
            END IF;

            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.certificate_id IS DISTINCT FROM OLD.certificate_id
               OR NEW.enrollment_id IS DISTINCT FROM OLD.enrollment_id
               OR NEW.snapshot_version IS DISTINCT FROM OLD.snapshot_version
               OR NEW.snapshot IS DISTINCT FROM OLD.snapshot
               OR NEW.snapshot_sha256 IS DISTINCT FROM OLD.snapshot_sha256
               OR NEW.original_storage_key IS DISTINCT FROM OLD.original_storage_key
               OR NEW.original_pdf_sha256 IS DISTINCT FROM OLD.original_pdf_sha256
               OR NEW.original_size_bytes IS DISTINCT FROM OLD.original_size_bytes
               OR NEW.rendered_at IS DISTINCT FROM OLD.rendered_at
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'certificate document snapshot/original artifact is immutable';
            END IF;

            IF OLD.status = 'SIGNED' THEN
                RAISE EXCEPTION 'signed certificate document is immutable';
            END IF;

            IF OLD.status <> 'PENDING_SIGNATURE' OR NEW.status <> 'SIGNED' THEN
                RAISE EXCEPTION 'only PENDING_SIGNATURE -> SIGNED transition is allowed';
            END IF;

            IF NEW.signed_storage_key IS NULL
               OR NEW.signed_pdf_sha256 IS NULL
               OR NEW.signed_size_bytes IS NULL
               OR NEW.signed_at IS NULL
               OR NEW.signature_provider IS NULL THEN
                RAISE EXCEPTION 'signed certificate document requires complete signature metadata';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_certificate_documents_immutable
        BEFORE UPDATE OR DELETE ON certificate_documents
        FOR EACH ROW EXECUTE FUNCTION protect_certificate_document_immutability()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_certificate_documents_immutable ON certificate_documents"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_certificate_document_immutability()")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_certificate_documents ON certificate_documents"
    )
    op.execute("ALTER TABLE certificate_documents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE certificate_documents DISABLE ROW LEVEL SECURITY")
    op.drop_index("uq_certificate_pending_signature_per_enrollment", table_name="certificates")
    op.drop_table("certificate_documents")
