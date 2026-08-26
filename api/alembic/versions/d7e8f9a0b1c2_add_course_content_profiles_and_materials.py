"""Add course_content_profiles and course_materials tables

Creates two new tables:
1. course_content_profiles — structured academic content extracted from
   apostilas, with provenance tracking and review status.
2. course_materials — course-level downloadable materials (apostilas PDFs)
   that are NOT tied to lessons and do NOT affect progress/completion.

Revision ID: d7e8f9a0b1c2
Revises: f8a9b0c1d2e3
Create Date: 2026-08-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_content_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False, unique=True, index=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("general_objective", sa.Text(), nullable=True),
        sa.Column("specific_objectives", postgresql.JSONB, nullable=True),
        sa.Column("prerequisites", sa.Text(), nullable=True),
        sa.Column("learning_outcomes", postgresql.JSONB, nullable=True),
        sa.Column("syllabus", postgresql.JSONB, nullable=True),
        sa.Column("modules", postgresql.JSONB, nullable=True),
        sa.Column("key_topics", postgresql.JSONB, nullable=True),
        sa.Column("risks_covered", postgresql.JSONB, nullable=True),
        sa.Column("prevention_topics", postgresql.JSONB, nullable=True),
        sa.Column("ppe_topics", postgresql.JSONB, nullable=True),
        sa.Column("emergency_topics", postgresql.JSONB, nullable=True),
        sa.Column("standards_referenced", postgresql.JSONB, nullable=True),
        sa.Column("assessment_summary", sa.Text(), nullable=True),
        sa.Column("recycling_summary", sa.Text(), nullable=True),
        sa.Column("validity_summary", sa.Text(), nullable=True),
        sa.Column("technical_responsible", sa.Text(), nullable=True),
        sa.Column("instructor_information", postgresql.JSONB, nullable=True),
        sa.Column("source_manifest", postgresql.JSONB, nullable=True),
        sa.Column("review_status", sa.String(), nullable=False, server_default="SOURCE_CONFIRMED"),
        sa.Column("review_required_fields", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "course_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False, server_default="application/pdf"),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=True, index=True),
        sa.Column("document_type", sa.String(), nullable=False, server_default="APOSTILA"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Unique constraint to prevent duplicate materials (same course + sha256)
    op.create_unique_constraint(
        "uq_course_material_tenant_course_sha",
        "course_materials",
        ["tenant_id", "course_id", "sha256"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_course_material_tenant_course_sha", "course_materials", type_="unique")
    op.drop_table("course_materials")
    op.drop_table("course_content_profiles")
