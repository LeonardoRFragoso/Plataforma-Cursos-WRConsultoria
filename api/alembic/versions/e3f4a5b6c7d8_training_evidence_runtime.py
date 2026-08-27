"""Add regulatory training evidence runtime.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "enrollment_compliance_progress",
    "practical_training_records",
    "training_access_events",
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    # A regulated course may explicitly not require a final assessment. The
    # electronic completion declaration must therefore be able to exist
    # without a fabricated AssessmentAttempt foreign key.
    op.alter_column(
        "student_signature_evidence",
        "assessment_attempt_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    op.create_table(
        "enrollment_compliance_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False, server_default="ENROLLED"),
        sa.Column("blockers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("state_updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_evaluated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "enrollment_id", name="uq_enrollment_compliance_progress"),
    )
    for column in ("tenant_id", "enrollment_id", "student_id", "course_id", "state"):
        op.create_index(f"ix_enrollment_compliance_progress_{column}", "enrollment_compliance_progress", [column])
    op.create_index(
        "ix_enrollment_compliance_tenant_state",
        "enrollment_compliance_progress",
        ["tenant_id", "state"],
    )

    op.create_table(
        "practical_training_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_professionals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("practical_training_records.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("performed_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("instructor_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "result IN ('PENDING','SATISFACTORY','UNSATISFACTORY')",
            name="ck_practical_training_result",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_practical_training_duration_positive",
        ),
    )
    for column in (
        "tenant_id", "enrollment_id", "student_id", "course_id", "instructor_id", "supersedes_id", "result"
    ):
        op.create_index(f"ix_practical_training_records_{column}", "practical_training_records", [column])
    op.create_index(
        "ix_practical_training_enrollment_time",
        "practical_training_records",
        ["tenant_id", "enrollment_id", "performed_at"],
    )

    op.create_table(
        "training_access_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in (
        "tenant_id", "enrollment_id", "student_id", "course_id", "lesson_id", "actor_user_id", "event_type", "occurred_at"
    ):
        op.create_index(f"ix_training_access_events_{column}", "training_access_events", [column])
    op.create_index(
        "ix_training_access_enrollment_time",
        "training_access_events",
        ["tenant_id", "enrollment_id", "occurred_at"],
    )
    op.create_index(
        "ix_training_access_course_time",
        "training_access_events",
        ["tenant_id", "course_id", "occurred_at"],
    )
    op.create_index(
        "ix_training_access_session",
        "training_access_events",
        ["tenant_id", "session_id"],
    )

    for table in _TABLES:
        _enable_rls(table)

    # Regulatory evidence is append-only. Corrections are represented by new
    # ledger/practical rows, never by rewriting or deleting history.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_regulatory_evidence_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("training_access_events", "practical_training_records"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION reject_regulatory_evidence_mutation()"
        )


def downgrade() -> None:
    for table in ("training_access_events", "practical_training_records"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_regulatory_evidence_mutation()")
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("training_access_events")
    op.drop_table("practical_training_records")
    op.drop_table("enrollment_compliance_progress")
    # Refuse to silently lose no-assessment evidence on downgrade: null rows
    # must be reconciled before restoring the older NOT NULL contract.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM student_signature_evidence
                WHERE assessment_attempt_id IS NULL
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade: signature evidence without assessment attempt exists';
            END IF;
        END $$;
        """
    )
    op.alter_column(
        "student_signature_evidence",
        "assessment_attempt_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
