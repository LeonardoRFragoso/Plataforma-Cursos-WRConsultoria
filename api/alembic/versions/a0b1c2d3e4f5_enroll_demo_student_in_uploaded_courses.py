"""Enroll WR demo student in courses with validated uploaded video content.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-27

This is an idempotent homologation data migration. It only affects the
existing WR demo account ``aluno2@wr.demo`` and the four NR courses whose
private-storage videos and playback were validated before this migration.
"""

from datetime import date, datetime, timedelta
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_EMAIL = "aluno2@wr.demo"
COURSE_CODES = ("NR-06-F", "NR-12-F", "NR-33-AUT", "NR-35-F")
CLASS_LOCATION = "DEMO-EAD-ASSESSMENT"


def _scalar(bind, sql: str, **params):
    return bind.execute(sa.text(sql), params).scalar_one_or_none()


def upgrade() -> None:
    bind = op.get_bind()

    tenant_id = _scalar(bind, "SELECT id FROM tenants WHERE slug = 'wr' LIMIT 1")
    if tenant_id is None:
        raise RuntimeError("WR tenant not found; cannot provision demo student journey")

    # RLS-aware migration context for tenant-scoped tables.
    bind.execute(
        sa.text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    bind.execute(sa.text("SELECT set_config('app.bypass_rls', '1', true)"))

    user_id = _scalar(
        bind,
        """
        SELECT id
        FROM users
        WHERE tenant_id = :tenant_id AND lower(email) = lower(:email)
        LIMIT 1
        """,
        tenant_id=tenant_id,
        email=DEMO_EMAIL,
    )
    if user_id is None:
        raise RuntimeError(f"Demo user {DEMO_EMAIL} not found")

    student_id = _scalar(
        bind,
        "SELECT id FROM students WHERE tenant_id = :tenant_id AND user_id = :user_id LIMIT 1",
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if student_id is None:
        raise RuntimeError(f"Student profile for {DEMO_EMAIL} not found")

    admin_id = _scalar(
        bind,
        """
        SELECT id
        FROM users
        WHERE tenant_id = :tenant_id
          AND role IN ('admin', 'super_admin')
          AND is_active = true
        ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, created_at
        LIMIT 1
        """,
        tenant_id=tenant_id,
    )
    if admin_id is None:
        raise RuntimeError("Active WR administrator not found")

    now = datetime.utcnow()
    start_date = date.today()
    end_date = start_date + timedelta(days=90)

    for code in COURSE_CODES:
        course_id = _scalar(
            bind,
            """
            SELECT id
            FROM courses
            WHERE tenant_id = :tenant_id AND code = :code AND is_active = true
            LIMIT 1
            """,
            tenant_id=tenant_id,
            code=code,
        )
        if course_id is None:
            raise RuntimeError(f"Required demo course {code} not found or inactive")

        existing_enrollment = _scalar(
            bind,
            """
            SELECT e.id
            FROM enrollments e
            JOIN classes c ON c.id = e.class_id
            WHERE e.tenant_id = :tenant_id
              AND e.student_id = :student_id
              AND c.tenant_id = :tenant_id
              AND c.course_id = :course_id
              AND e.status IN ('CONFIRMADA', 'CONCLUIDA')
            ORDER BY e.enrollment_date DESC
            LIMIT 1
            """,
            tenant_id=tenant_id,
            student_id=student_id,
            course_id=course_id,
        )
        if existing_enrollment is not None:
            continue

        class_id = _scalar(
            bind,
            """
            SELECT id
            FROM classes
            WHERE tenant_id = :tenant_id
              AND course_id = :course_id
              AND location = :location
            ORDER BY created_at
            LIMIT 1
            """,
            tenant_id=tenant_id,
            course_id=course_id,
            location=CLASS_LOCATION,
        )

        if class_id is None:
            class_id = uuid4()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO classes (
                        id, tenant_id, course_id, responsible_admin_id,
                        start_date, end_date, max_students, location,
                        status, description, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :course_id, :admin_id,
                        :start_date, :end_date, 1000, :location,
                        'ABERTA', :description, :now, :now
                    )
                    """
                ),
                {
                    "id": class_id,
                    "tenant_id": tenant_id,
                    "course_id": course_id,
                    "admin_id": admin_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": CLASS_LOCATION,
                    "description": "Turma técnica de homologação do fluxo aluno → vídeo → avaliação → certificado.",
                    "now": now,
                },
            )

        bind.execute(
            sa.text(
                """
                INSERT INTO enrollments (
                    id, tenant_id, student_id, class_id, status, source,
                    enrollment_date, price, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :student_id, :class_id,
                    'CONFIRMADA', 'INDIVIDUAL', :now, 0.0, :now, :now
                )
                ON CONFLICT (tenant_id, student_id, class_id) DO NOTHING
                """
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "student_id": student_id,
                "class_id": class_id,
                "now": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    tenant_id = _scalar(bind, "SELECT id FROM tenants WHERE slug = 'wr' LIMIT 1")
    if tenant_id is None:
        return

    bind.execute(
        sa.text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    bind.execute(sa.text("SELECT set_config('app.bypass_rls', '1', true)"))

    student_id = _scalar(
        bind,
        """
        SELECT s.id
        FROM students s
        JOIN users u ON u.id = s.user_id
        WHERE s.tenant_id = :tenant_id
          AND u.tenant_id = :tenant_id
          AND lower(u.email) = lower(:email)
        LIMIT 1
        """,
        tenant_id=tenant_id,
        email=DEMO_EMAIL,
    )
    if student_id is None:
        return

    bind.execute(
        sa.text(
            """
            DELETE FROM enrollments e
            USING classes c, courses co
            WHERE e.class_id = c.id
              AND c.course_id = co.id
              AND e.tenant_id = :tenant_id
              AND c.tenant_id = :tenant_id
              AND co.tenant_id = :tenant_id
              AND e.student_id = :student_id
              AND e.price = 0.0
              AND c.location = :location
              AND co.code IN ('NR-06-F', 'NR-12-F', 'NR-33-AUT', 'NR-35-F')
            """
        ),
        {
            "tenant_id": tenant_id,
            "student_id": student_id,
            "location": CLASS_LOCATION,
        },
    )

    bind.execute(
        sa.text(
            """
            DELETE FROM classes c
            USING courses co
            WHERE c.course_id = co.id
              AND c.tenant_id = :tenant_id
              AND co.tenant_id = :tenant_id
              AND c.location = :location
              AND co.code IN ('NR-06-F', 'NR-12-F', 'NR-33-AUT', 'NR-35-F')
              AND NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.class_id = c.id)
            """
        ),
        {"tenant_id": tenant_id, "location": CLASS_LOCATION},
    )
