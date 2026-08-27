"""audit corporate employee membership changes

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f5
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "corporate_employee_link_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["previous_company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_corporate_link_event_tenant", "corporate_employee_link_events", ["tenant_id"])
    op.create_index("ix_corporate_link_event_student", "corporate_employee_link_events", ["student_id"])
    op.create_index("ix_corporate_link_event_company", "corporate_employee_link_events", ["company_id"])
    op.create_index("ix_corporate_link_event_previous_company", "corporate_employee_link_events", ["previous_company_id"])
    op.create_index("ix_corporate_link_event_created", "corporate_employee_link_events", ["created_at"])

    op.execute("ALTER TABLE corporate_employee_link_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE corporate_employee_link_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_corporate_employee_link_events
        ON corporate_employee_link_events
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            OR current_setting('app.bypass_rls', true) = '1'
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            OR current_setting('app.bypass_rls', true) = '1'
        )
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_student_company_membership()
        RETURNS trigger AS $$
        DECLARE
            previous_company uuid;
            next_company uuid;
            action_value text;
            actor_value uuid;
            reason_value text;
            actor_text text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.company_id IS NULL THEN
                    RETURN NEW;
                END IF;
                previous_company := NULL;
                next_company := NEW.company_id;
                action_value := 'LINKED';
            ELSE
                IF OLD.company_id IS NOT DISTINCT FROM NEW.company_id THEN
                    RETURN NEW;
                END IF;
                previous_company := OLD.company_id;
                next_company := NEW.company_id;
                IF OLD.company_id IS NULL AND NEW.company_id IS NOT NULL THEN
                    action_value := 'LINKED';
                ELSIF OLD.company_id IS NOT NULL AND NEW.company_id IS NULL THEN
                    action_value := 'UNLINKED';
                ELSE
                    action_value := 'TRANSFERRED';
                END IF;
            END IF;

            actor_text := NULLIF(current_setting('app.current_user_id', true), '');
            IF actor_text IS NOT NULL THEN
                BEGIN
                    actor_value := actor_text::uuid;
                EXCEPTION WHEN invalid_text_representation THEN
                    actor_value := NULL;
                END;
            END IF;
            reason_value := NULLIF(current_setting('app.corporate_link_reason', true), '');

            INSERT INTO corporate_employee_link_events (
                id, tenant_id, student_id, previous_company_id, company_id,
                action, reason, actor_user_id, created_at
            ) VALUES (
                gen_random_uuid(), NEW.tenant_id, NEW.id, previous_company, next_company,
                action_value, reason_value, actor_value, CURRENT_TIMESTAMP
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_student_company_membership
        AFTER INSERT OR UPDATE OF company_id ON students
        FOR EACH ROW EXECUTE FUNCTION audit_student_company_membership()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_student_company_membership ON students")
    op.execute("DROP FUNCTION IF EXISTS audit_student_company_membership()")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_corporate_employee_link_events ON corporate_employee_link_events")
    op.drop_table("corporate_employee_link_events")
