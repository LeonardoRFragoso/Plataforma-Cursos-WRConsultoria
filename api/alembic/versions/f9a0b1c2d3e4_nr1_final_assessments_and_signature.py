"""NR-01 final assessment attempts and student completion evidence

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.create_table(
        "assessment_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("question_version", sa.String(), nullable=False, server_default="wr-nr-demo-v1"),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("correct_answers", sa.Integer(), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("minimum_score", sa.Float(), nullable=False, server_default="70"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("enrollment_id", "attempt_number", name="uq_assessment_enrollment_attempt"),
    )
    op.create_index("ix_assessment_attempts_tenant_id", "assessment_attempts", ["tenant_id"])
    op.create_index("ix_assessment_attempts_enrollment_id", "assessment_attempts", ["enrollment_id"])
    op.create_index("ix_assessment_attempts_student_id", "assessment_attempts", ["student_id"])
    op.create_index("ix_assessment_attempts_course_id", "assessment_attempts", ["course_id"])

    op.create_table(
        "student_signature_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enrollments.id"), nullable=False, unique=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("assessment_attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessment_attempts.id"), nullable=False),
        sa.Column("declaration_version", sa.String(), nullable=False, server_default="nr1-demo-v1"),
        sa.Column("auth_method", sa.String(), nullable=False, server_default="PASSWORD_REAUTH"),
        sa.Column("accepted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_student_signature_evidence_tenant_id", "student_signature_evidence", ["tenant_id"])
    op.create_index("ix_student_signature_evidence_enrollment_id", "student_signature_evidence", ["enrollment_id"])
    op.create_index("ix_student_signature_evidence_student_id", "student_signature_evidence", ["student_id"])
    op.create_index("ix_student_signature_evidence_course_id", "student_signature_evidence", ["course_id"])

    _enable_rls("assessment_attempts")
    _enable_rls("student_signature_evidence")


def downgrade() -> None:
    for table in ("student_signature_evidence", "assessment_attempts"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("student_signature_evidence")
    op.drop_table("assessment_attempts")
