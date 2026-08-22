"""normalize existing emails to lowercase with collision detection

Revision ID: f2a3b4c5d6e7
Revises: a1b3c4d5e6f7
Create Date: 2026-08-22

Normalizes all User.email values to trimmed lowercase to match the
application-level normalize_email() helper. Before updating, detects
case-variant collisions within the same tenant (e.g. User@Test.com and
user@test.com in the same tenant) and fails loudly with a clear error
requiring manual reconciliation.

Also creates a unique index on (tenant_id, lower(email)) to enforce
case-insensitive uniqueness at the database level going forward, while
keeping the existing case-sensitive unique constraint for compatibility.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "a1b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Detect case-variant collisions within the same tenant.
    #    If any exist, fail loudly — we must not silently merge users.
    conn = op.get_bind()

    collisions = conn.execute(
        sa.text(
            """
            SELECT tenant_id, lower(trim(email)) as norm_email,
                   count(*) as cnt,
                   string_agg(email, ', ') as variants
            FROM users
            GROUP BY tenant_id, lower(trim(email))
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    if collisions:
        details = "; ".join(
            f"tenant={row.tenant_id}, normalized={row.norm_email}, "
            f"variants=[{row.variants}]"
            for row in collisions
        )
        raise RuntimeError(
            "Cannot normalize emails: case-variant collisions detected "
            f"within the same tenant. Manual reconciliation required: {details}"
        )

    # 2. Normalize all emails to trimmed lowercase.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET email = lower(trim(email))
            WHERE email != lower(trim(email))
            """
        )
    )

    # 3. Create a unique index on (tenant_id, lower(email)) to enforce
    #    case-insensitive uniqueness at the DB level going forward.
    #    This complements the existing case-sensitive unique constraint
    #    and prevents future case-variant duplicates.
    op.create_index(
        "ux_user_tenant_email_lower",
        "users",
        ["tenant_id", sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_user_tenant_email_lower", table_name="users")
    # We do NOT reverse the email normalization — that would re-introduce
    # mixed-case data. The data change is irreversible by design.
