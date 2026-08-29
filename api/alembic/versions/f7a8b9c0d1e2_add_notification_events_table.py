"""add notification events table for email idempotency

Revision ID: f7a8b9c0d1e2
Revises: 1ba7b99712b3
Create Date: 2026-08-29

Creates the notification_events table used by the idempotency service
to prevent duplicate transactional email deliveries (duplicate webhooks,
retries, concurrent handlers).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "1ba7b99712b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("dedup_key", sa.String(256), nullable=False),
        sa.Column("notification_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="SENT"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_events_dedup_key", "notification_events", ["dedup_key"], unique=True)
    op.create_index("ix_notification_events_tenant_type", "notification_events", ["tenant_id", "notification_type"])
    op.create_index("ix_notification_events_created_at", "notification_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_events_created_at", table_name="notification_events")
    op.drop_index("ix_notification_events_tenant_type", table_name="notification_events")
    op.drop_index("ix_notification_events_dedup_key", table_name="notification_events")
    op.drop_table("notification_events")
