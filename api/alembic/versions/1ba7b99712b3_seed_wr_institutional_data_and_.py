"""seed_wr_institutional_data_and_instructor

Revision ID: 1ba7b99712b3
Revises: e784adb04d36
Create Date: 2026-08-28 17:58:36.817644

Seeds WR institutional data (razão social, CNPJ, endereço) on the WR
tenant and creates the informed instructor (Willy Ramos) as a
TrainingProfessional with technical responsibility PENDING_VERIFICATION.

IMPORTANT:
- CEO is NOT a technical qualification. Willy Ramos is registered as
  an informed instructor only. Technical responsibility for NR-10
  (electrical) and NR-12 (PLH) remains PENDING_VERIFICATION.
- No MTE/CREA/CFT/electrical formation/PLH/proficiency/ICP-Brasil
  registrations are invented.
"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ba7b99712b3"
down_revision: Union[str, None] = "e784adb04d36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WR_TENANT_SLUG = "wr"

WR_INSTITUTIONAL = {
    "legal_name": "WR Consultoria e Soluções em QSMS Ltda",
    "cnpj": "51.492.324/0001-25",
    "address": {
        "street": "Avenida Paranapuã, 1680, sala 205",
        "neighborhood": "Praia da Bandeira",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "zip_code": "21910-174",
    },
}

# Instructor — informed only, NOT a verified technical responsible.
# Qualification: Técnico em Segurança do Trabalho (NOT electrical, NOT PLH).
# Corporate role: CEO (NOT a technical qualification).
INSTRUCTOR_CPF = "00000000000"  # Placeholder — must be replaced with real CPF


def upgrade() -> None:
    bind = op.get_bind()

    # Update WR tenant with institutional data.
    result = bind.execute(
        sa.text("SELECT id, settings FROM tenants WHERE slug = :slug"),
        {"slug": WR_TENANT_SLUG},
    )
    row = result.fetchone()
    if row:
        tenant_id = row[0]
        settings = row[1] if row[1] else {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        settings["institutional"] = WR_INSTITUTIONAL
        bind.execute(
            sa.text("UPDATE tenants SET legal_name = :legal_name, cnpj = :cnpj, settings = :settings WHERE id = :tid"),
            {
                "legal_name": WR_INSTITUTIONAL["legal_name"],
                "cnpj": WR_INSTITUTIONAL["cnpj"],
                "settings": json.dumps(settings),
                "tid": str(tenant_id),
            },
        )

        # Create instructor as TrainingProfessional if not exists.
        # professional_registration is NULL — PENDING_VERIFICATION.
        # No MTE/CREA/CFT/electrical/PLH registrations are invented.
        existing = bind.execute(
            sa.text("SELECT id FROM training_professionals WHERE tenant_id = :tid AND cpf = :cpf"),
            {"tid": str(tenant_id), "cpf": INSTRUCTOR_CPF},
        ).fetchone()
        if not existing:
            bind.execute(
                sa.text(
                    "INSERT INTO training_professionals (id, tenant_id, full_name, cpf, qualification, professional_registration, council, registration_state, is_active, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :tid, :full_name, :cpf, :qualification, NULL, NULL, NULL, true, now(), now())"
                ),
                {
                    "tid": str(tenant_id),
                    "full_name": "Willy Ramos",
                    "cpf": INSTRUCTOR_CPF,
                    "qualification": "Técnico em Segurança do Trabalho",
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id FROM tenants WHERE slug = :slug"),
        {"slug": WR_TENANT_SLUG},
    )
    row = result.fetchone()
    if row:
        tenant_id = row[0]
        bind.execute(
            sa.text("DELETE FROM training_professionals WHERE tenant_id = :tid AND cpf = :cpf"),
            {"tid": str(tenant_id), "cpf": INSTRUCTOR_CPF},
        )
        # Restore settings without institutional block
        settings_row = bind.execute(
            sa.text("SELECT settings FROM tenants WHERE id = :tid"),
            {"tid": str(tenant_id)},
        ).fetchone()
        if settings_row and settings_row[0]:
            settings = settings_row[0] if isinstance(settings_row[0], dict) else json.loads(settings_row[0])
            settings.pop("institutional", None)
            bind.execute(
                sa.text("UPDATE tenants SET legal_name = NULL, cnpj = NULL, settings = :settings WHERE id = :tid"),
                {"settings": json.dumps(settings), "tid": str(tenant_id)},
            )
